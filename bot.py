import os
import random
import asyncio
import sqlite3
import requests
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from deep_translator import GoogleTranslator

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ===== TOKEN CONFIGURATION =====
SUOLALA_CONTRACT = "CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
PAIR_ADDRESS = "79Qaq5b1JfC8bFuXkAvXTR67fRPmMjMVNkEA3bb8bLzi"
DEXSCREENER_PAIR_API = f"https://api.dexscreener.com/latest/dex/pairs/solana/{PAIR_ADDRESS}"
DEXSCREENER_TOKEN_API = f"https://api.dexscreener.com/latest/dex/tokens/{SUOLALA_CONTRACT}"
MIN_BUY_AMOUNT = 100  # Minimum $ amount to trigger alert

MAGICEDEN_COLLECTION = "suolala_"
MAGICEDEN_LIST_URL = "https://api-mainnet.magiceden.dev/v2/collections/{}/listings?offset=0&limit=100"

# ===== BOT TOKEN =====
TOKEN = os.getenv("BOT_TOKEN")

# ===== TIMEZONE =====
CHINA_TZ = ZoneInfo("Asia/Shanghai")

# ===== MEMORY =====
KNOWN_CHATS_FILE = "known_chats.txt"
KNOWN_CHATS = set()
LAST_GM_DATE = None
LAST_GN_DATE = None
USED_MOTIVATIONS = {}
LAST_CHECKED_TIME = None

if os.path.exists(KNOWN_CHATS_FILE):
    with open(KNOWN_CHATS_FILE, "r") as f:
        KNOWN_CHATS = set(map(int, f.read().splitlines()))

# ===== DATABASE =====
db = sqlite3.connect("weekly_stats.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER,
    chat_id INTEGER,
    year_week TEXT,
    count INTEGER,
    PRIMARY KEY (user_id, chat_id, year_week)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT
)
""")
db.commit()

def current_week():
    y, w, _ = datetime.utcnow().isocalendar()
    return f"{y}-W{w:02d}"

# ===== DELETE HELPER =====
async def delete_after_delay(message, delay=300):
    """Delete a message after specified delay in seconds"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

# ===== SAVE CHAT =====
def remember_chat(update: Update):
    if update and update.effective_chat:
        cid = update.effective_chat.id
        if cid not in KNOWN_CHATS:
            KNOWN_CHATS.add(cid)
            with open(KNOWN_CHATS_FILE, "a") as f:
                f.write(str(cid) + "\n")

# ===== QR HELPER =====
async def send_qr_if_exists(update, name):
    path = f"qrcodes/{name}.jpg"
    if os.path.exists(path):
        await update.message.reply_photo(photo=open(path, "rb"))

# ===== TRANSLATE =====
async def translate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Reply to a message and type /translate")
        return

    original = update.message.reply_to_message.text
    if not original:
        await update.message.reply_text("❗ Nothing to translate")
        return

    try:
        translated = GoogleTranslator(source="auto", target="en").translate(original)
        flag = "🇬🇧"

        if translated.strip().lower() == original.strip().lower():
            translated = GoogleTranslator(source="auto", target="zh-CN").translate(original)
            flag = "🇨🇳"

        sent = await update.message.reply_text(f"{flag} Translation:\n{translated}")
        await asyncio.sleep(40)
        await sent.delete()
    except:
        await update.message.reply_text("❌ Translation failed")

# ===== MESSAGE TRACKER =====
async def track_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.is_bot:
        return
    if update.effective_chat.type == "private":
        return

    user = update.effective_user

    cur.execute("""
    INSERT INTO users (user_id, username, first_name)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id)
    DO UPDATE SET username=excluded.username, first_name=excluded.first_name
    """, (user.id, user.username, user.first_name))

    cur.execute("""
    INSERT INTO stats (user_id, chat_id, year_week, count)
    VALUES (?, ?, ?, 1)
    ON CONFLICT(user_id, chat_id, year_week)
    DO UPDATE SET count = count + 1
    """, (user.id, update.effective_chat.id, current_week()))

    db.commit()

# ===== TOKEN BUY MONITORING =====
async def check_large_buys(app):
    """Background task to check for large token buys"""
    global LAST_CHECKED_TIME
    
    while True:
        try:
            print("🔍 Checking for large buys...")
            
            # Fetch pair data from DexScreener
            response = requests.get(DEXSCREENER_PAIR_API, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                pair = data.get('pair', {})
                
                if not pair:
                    print("❌ No pair data found")
                    await asyncio.sleep(30)
                    continue
                
                # Get current price and market data
                price_usd = float(pair.get('priceUsd', 0))
                market_cap = float(pair.get('marketCap', 0))
                liquidity_usd = float(pair.get('liquidity', {}).get('usd', 0))
                
                # Try to get transactions from different sources
                transactions = []
                
                # Method 1: Check if there are transactions in the pair data
                if 'txns' in pair and 'h24' in pair['txns']:
                    transactions = pair['txns']['h24'].get('transactions', [])
                    print(f"📊 Found {len(transactions)} transactions in h24 data")
                
                # If no transactions found, try alternative method
                if not transactions:
                    # Try to get recent trades from the API
                    trades_url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{PAIR_ADDRESS}/trades"
                    trades_response = requests.get(trades_url, timeout=10)
                    
                    if trades_response.status_code == 200:
                        trades_data = trades_response.json()
                        if 'trades' in trades_data:
                            transactions = trades_data['trades']
                            print(f"📊 Found {len(transactions)} trades in trades endpoint")
                
                # Process transactions
                if transactions:
                    # Sort by timestamp (newest first)
                    sorted_txs = sorted(transactions, 
                                      key=lambda x: x.get('timestamp', 0), 
                                      reverse=True)
                    
                    # Check only the newest 10 transactions
                    for tx in sorted_txs[:10]:
                        tx_type = tx.get('side', '').lower()  # Some APIs use 'side' instead of 'txType'
                        if not tx_type:
                            tx_type = tx.get('txType', '').lower()
                        
                        # Calculate USD value
                        tx_amount = float(tx.get('amount', 0))
                        tx_quote_amount = float(tx.get('quoteAmount', 0))
                        
                        # Try to get USD value directly or calculate it
                        usd_value = float(tx.get('usdValue', 0))
                        if usd_value == 0 and tx_quote_amount > 0:
                            # Estimate USD value from SOL amount (rough estimate)
                            # SOL price is approximately $100, but we need a better method
                            sol_price = 100  # Rough estimate
                            usd_value = tx_quote_amount * sol_price
                        
                        tx_hash = tx.get('txHash') or tx.get('transactionId') or tx.get('id', '')
                        
                        # Check if this is a buy and meets threshold
                        if tx_type in ['buy', 'b'] and usd_value >= MIN_BUY_AMOUNT:
                            # Check if we've processed this recently
                            if tx_hash:
                                # Check in memory and file
                                processed_file = "processed_buys.txt"
                                processed = set()
                                
                                if os.path.exists(processed_file):
                                    with open(processed_file, "r") as f:
                                        processed = set(f.read().splitlines())
                                
                                if tx_hash not in processed:
                                    print(f"✅ Detected large buy: ${usd_value:.2f} - Hash: {tx_hash[:20]}")
                                    
                                    # Send alert
                                    await send_buy_alert(app, tx, pair, usd_value)
                                    
                                    # Mark as processed
                                    processed.add(tx_hash)
                                    with open(processed_file, "a") as f:
                                        f.write(tx_hash + "\n")
                                    
                                    break  # Send only one alert per check
                else:
                    print("⚠️ No transactions found in API response")
                    
            else:
                print(f"❌ API Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error checking buys: {e}")
        
        # Wait before next check
        await asyncio.sleep(30)

async def send_buy_alert(app, transaction, pair_data, usd_value):
    """Send buy alert to all known chats"""
    try:
        # Extract transaction data
        tx_hash = transaction.get('txHash') or transaction.get('transactionId') or transaction.get('id', 'unknown')
        buyer_address = transaction.get('buyer') or transaction.get('maker') or "Unknown"
        
        # Get amounts
        token_amount = float(transaction.get('amount', 0))
        sol_amount = float(transaction.get('quoteAmount', 0))
        
        # Format buyer address
        if buyer_address != "Unknown" and len(buyer_address) > 10:
            short_buyer = f"{buyer_address[:6]}...{buyer_address[-4:]}"
        else:
            short_buyer = buyer_address
        
        # Determine buyer category
        if usd_value >= 1000:
            category = "🐋 Whale ($1,000+)"
        elif usd_value >= 250:
            category = "🦈 Shark ($250-$1,000)"
        else:
            category = "🐟 Fish ($100-$250)"
        
        # Get token price and market cap
        price_usd = float(pair_data.get('priceUsd', 0))
        market_cap = float(pair_data.get('marketCap', 0))
        
        # Try to get price change
        price_change = 0
        if 'priceChange' in pair_data:
            if isinstance(pair_data['priceChange'], dict):
                price_change = float(pair_data['priceChange'].get('h24', 0))
            else:
                price_change = float(pair_data['priceChange'])
        
        # Format amounts
        if token_amount >= 1000000:
            formatted_token_amount = f"{token_amount/1000000:.2f}M"
        elif token_amount >= 1000:
            formatted_token_amount = f"{token_amount/1000:.2f}K"
        else:
            formatted_token_amount = f"{token_amount:,.0f}"
            
        formatted_usd_value = "${:,.2f}".format(usd_value)
        formatted_sol_amount = "{:.3f}".format(sol_amount)
        
        if price_usd < 0.0001:
            formatted_price = "${:.8f}".format(price_usd)
        elif price_usd < 0.01:
            formatted_price = "${:.6f}".format(price_usd)
        else:
            formatted_price = "${:.4f}".format(price_usd)
            
        formatted_market_cap = "${:,.2f}".format(market_cap)
        
        # Create caption
        caption = (
            "🚀 **SUOLALA / SOL BUY ALERT** ✅\n\n"
            f"💰 **Bought:** {formatted_token_amount} SUOLALA\n"
            f"💸 **Paid:** {formatted_sol_amount} SOL ≈ {formatted_usd_value}\n"
            f"👤 **Buyer:** `{short_buyer}`\n"
            f"🏷️ **Buyer Category:** {category}\n\n"
            f"📊 **Price:** {formatted_price}\n"
            f"🏦 **Market Cap:** {formatted_market_cap}\n"
            f"📈 **24h Change:** {price_change:+.2f}%\n\n"
        )
        
        # Add transaction link if we have hash
        if tx_hash != "unknown" and len(tx_hash) > 10:
            caption += f"🔍 **Check on Solscan:**\nhttps://solscan.io/tx/{tx_hash}\n\n"
        
        caption += "🔄 **TRADE $SUOLALA on Jupiter!**\nhttps://jup.ag/swap/SOL-CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
        
        # Send to all known chats
        for chat_id in KNOWN_CHATS:
            try:
                # Try to send with image first
                if os.path.exists("buy.png"):
                    with open("buy.png", "rb") as photo:
                        await app.bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=caption,
                            parse_mode="Markdown"
                        )
                        print(f"✅ Buy alert sent to chat {chat_id} with buy.png")
                else:
                    # If no image, send as text
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        parse_mode="Markdown"
                    )
                    print(f"⚠️ Buy alert sent to chat {chat_id} (no buy.png found)")
                    
            except Exception as e:
                print(f"❌ Failed to send buy alert to chat {chat_id}: {e}")
                
    except Exception as e:
        print(f"❌ Error in send_buy_alert: {e}")

# ===== BASIC COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "🤖 SUOLALA Bot 🐉\n"
        "Official Solana China meme coin 🇨🇳🔥\n\n"
        "Commands:\n"
        "/price /chart /buy /memes /stickers\n"
        "/x /community /nft /contract /website /rules\n"
        "/suolala /motivate /count /top /randomnft\n"
        "/testbuy /buystats"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "💰 SUOLALA Price\n"
        "https://dexscreener.com/solana/79Qaq5b1JfC8bFuXkAvXTR67fRPmMjMVNkEA3bb8bLzi"
    )
    await send_qr_if_exists(update, "price")

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "📈 SUOLALA Chart\n"
        "https://dexscreener.com/solana/79Qaq5b1JfC8bFuXkAvXTR67fRPmMjMVNkEA3bb8bLzi"
    )
    await send_qr_if_exists(update, "chart")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    
    try:
        await context.bot.send_animation(
            chat_id=update.effective_chat.id,
            animation=open("buy.gif", "rb"),
            caption=
        "╔══════════════════════════════╗\n"
        "        🚀 HOW TO BUY SUOLALA\n"
        "╚══════════════════════════════╝\n\n"
        "👛 ① Create a Phantom Wallet\n"
        "💰 ② Buy SOL & fund your wallet\n"
        "🪐 ③ Open Jupiter Exchange\n"
        "🔗 https://jup.ag\n"
        "📋 ④ Paste the SUOLALA Contract\n"
        "🔁 ⑤ Swap SOL ➜ SUOLALA\n\n"
        "═══════════════════════════════\n"
        "📜 OFFICIAL CONTRACT ADDRESS\n"
        "CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8\n"
        "═══════════════════════════════"
        )
    except:
        await update.message.reply_text(
        "╔══════════════════════════════╗\n"
        "        🚀 HOW TO BUY SUOLALA\n"
        "╚══════════════════════════════╝\n\n"
        "👛 ① Create a Phantom Wallet\n"
        "💰 ② Buy SOL & fund your wallet\n"
        "🪐 ③ Open Jupiter Exchange\n"
        "🔗 https://jup.ag\n"
        "📋 ④ Paste the SUOLALA Contract\n"
        "🔁 ⑤ Swap SOL ➜ SUOLALA\n\n"
        "═══════════════════════════════\n"
        "📜 OFFICIAL CONTRACT ADDRESS\n"
        "CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8\n"
        "═══════════════════════════════"
        )
    
    await send_qr_if_exists(update, "buy")

async def memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text("😂 Memes\nhttps://t.me/suolala_memes")
    await send_qr_if_exists(update, "memes")

async def stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "🧧 Stickers\n"
        "Static: https://t.me/addstickers/suolalastickers\n"
        "Animated: https://t.me/addstickers/Suolala_cto\n"
        "Animated: https://t.me/addstickers/suolalaanimatedstickers"
    )

async def x(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text("🐦 X\nhttps://x.com/suolalax")
    await send_qr_if_exists(update, "x")

async def community(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "👥 Community\nhttps://twitter.com/i/communities/1980324795851186529"
    )
    await send_qr_if_exists(update, "community")
    
async def nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)

    caption = (
        "🚀 索拉拉 | Suolala NFT is LIVE\n\n"
        "索拉拉 is the premier Chinese ticker on Solana, inspired by Lily Liu "
        "and built by real builders 🔨💜\n\n"
        "💡 CTO Project\n"
        "❌ No VC\n"
        "❌ No whales\n"
        "✅ Community-driven\n\n"
        "After months where many memecoins died, 索拉拉 is still alive — "
        "powered purely by belief and builders.\n\n"
        "🎨 Why Suolala NFT?\n"
        "• Strengthen community unity\n"
        "• Increase brand visibility\n"
        "• 🔥 Burn 索拉拉 tokens\n\n"
        "🪙 Mint Info\n"
        "• Mint with a small amount of 索拉拉\n"
        "• 🔥 All mint tokens are burned\n"
        "• ~$1 SOL fee (LaunchMyNFT)\n\n"
        "🔗 Mint here:\n"
        "https://launchmynft.io/collections/wNeq7jJgwz89yDdXGje5AZGJtfknHmxwYijecMhDoSQ/TYrJFpW1PtmXoQWPtXXv\n\n"
        "🏃 让我们奔跑吧索拉拉们\n"
        "Built by builders. Alive by belief."
    )

    try:
        with open("nft.jpg", "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=caption
            )
    except:
        await update.message.reply_text(caption)

async def contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "📜 Contract\nCY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )
    await send_qr_if_exists(update, "contract")

async def website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "🌐 Website\nhttps://trends.fun/token/CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )
    await send_qr_if_exists(update, "website")
    
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "📌 Rules\nNo spam | No scams | No fake links | Respect all"
    )

# ===== RANDOM IMAGE =====
async def suolala(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    IMAGE_DIR = "girls"
    if os.path.exists(IMAGE_DIR):
        images = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(("jpg","png","jpeg"))]
        if images:
            img = random.choice(images)
            await update.message.reply_photo(open(f"{IMAGE_DIR}/{img}", "rb"))
        else:
            await update.message.reply_text("No images found in girls directory")
    else:
        await update.message.reply_text("Girls directory not found")

# ===== MOTIVATIONS =====
MOTIVATIONS = [
    "🐉 SUOLALA is built by those who stay 💎",
    "💎 Holding SUOLALA means trusting your own vision 🔮",
    "🔥 Strong hands don't look for exits — they build 🛡️",
    "🚀 SUOLALA moves when patience beats panic ⏳",
    "🧠 Calm minds protect SUOLALA better than hype 🧘",
    "💪 If holding was easy, everyone would own SUOLALA 🐉",
    "⏰ Time rewards SUOLALA believers 💎",
    "🌊 Noise fades. SUOLALA remains 🛡️",
    "🐲 SUOLALA doesn't rush — it rises ⬆️",
    "📈 Price moves fast. Conviction lasts longer 🧠",
    "💎 Staying is harder than buying — that's the edge ⚔️",
    "🔥 Belief turns SUOLALA from meme to movement 🚀",
    "🛡️ Calm holders build lasting SUOLALA value 💎",
    "⏳ Staying power beats timing luck 🍀",
    "🐉 Those who stay define SUOLALA 💎",
    "🧠 Discipline keeps SUOLALA strong 🎯",
    "🚀 Growth rewards patience in SUOLALA 🌱",
    "💪 Weak hands react. Strong hands remain 🛡️",
    "🐲 SUOLALA stands firm through noise 🔕",
    "💎 Conviction builds SUOLALA over time ⏰",
    "🧠 Emotion exits early. Discipline stays longer 🔒",
    "🚀 SUOLALA isn't loud — it's persistent ⏳",
    "🐲 Those who stay early shape what comes later 🔮",
    "📈 Growth rewards those who don't rush it 🧘",
    "💪 Holding SUOLALA is choosing conviction over comfort 🔥",
    "🔥 Real progress looks boring at first 🌱",
    "🛡️ Calm holders build lasting value 💎",
    "⏳ Time tests everyone. SUOLALA holders pass 🏆",
    "🐉 SUOLALA survives because belief survives 🔋",
    "💎 Strong hands are made, not found ⚒️",
    "🧠 Focus beats fear every cycle 🔁",
    "🚀 SUOLALA grows when patience wins 🌱",
    "🔥 Community matters more than charts 📊",
    "🛡️ Stability is a hidden advantage 🎯",
    "💪 SUOLALA is held by those who understand waiting ⏰",
    "🐲 Memes move fast. Conviction moves further 🚀",
    "💎 SUOLALA is built on belief, not noise 🔕",
    "🧠 The strongest move is often doing nothing 🧘",
    "🔥 Patience separates SUOLALA holders from tourists 🧭",
    "💎 Long vision gives SUOLALA real strength 🧠",
    "🐉 Real believers stay when charts are quiet 🌊",
    "🚀 SUOLALA grows through time, not hype ⏳",
    "🛡️ Calm strategy protects SUOLALA value 💎",
    "💪 Staying disciplined builds SUOLALA slowly 🧱",
    "⏰ Time is the ally of SUOLALA holders 💎",
    "🔥 Conviction outlasts volatility in SUOLALA 🌊",
    "🧠 Strong mindset keeps SUOLALA steady 🎯",
    "🐲 Those who wait patiently shape SUOLALA's future 💎",
    "🐉 SUOLALA is built by patience, not pressure 💎",
    "💎 Those who believe early give SUOLALA its strength 🔥",
    "🚀 SUOLALA grows when holders stay focused ⏳",
    "🧠 Calm thinking keeps SUOLALA moving forward 🎯",
    "💪 SUOLALA rewards those who don't rush 🛡️",
    "🔥 Real support is holding, not talking 🐉",
    "⏰ Time and belief shape SUOLALA together 💎",
    "🛡️ Strong holders protect SUOLALA's future 🔒",
    "🐲 SUOLALA stands firm when noise gets loud 🌊",
    "💎 Trust the process — SUOLALA is still building 🧱",
    "🚀 SUOLALA moves best with steady hands ⏳",
    "🧠 Discipline today strengthens SUOLALA tomorrow 💎",
    "🔥 Community belief keeps SUOLALA alive 🐉",
    "💪 Holding SUOLALA means trusting your choice 🛡️",
    "⏰ Long vision gives SUOLALA real value 💎",
    "🐲 SUOLALA grows quietly before big moves 🔥",
    "🛡️ Calm holders build lasting SUOLALA strength 💎",
    "🚀 SUOLALA is a journey, not a quick flip ⏳",
    "💎 Staying consistent builds SUOLALA confidence 🧠",
    "🐉 Those who stay patient shape SUOLALA's path 💎",
]

async def motivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    chat_id = update.effective_chat.id
    used = USED_MOTIVATIONS.setdefault(chat_id, set())

    if len(used) >= len(MOTIVATIONS):
        used.clear()

    idx = random.choice([i for i in range(len(MOTIVATIONS)) if i not in used])
    used.add(idx)
    await update.message.reply_text(MOTIVATIONS[idx])

# ===== /count =====
async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute(
        "SELECT count FROM stats WHERE user_id=? AND chat_id=? AND year_week=?",
        (update.effective_user.id, update.effective_chat.id, current_week())
    )
    row = cur.fetchone()
    await update.message.reply_text(f"📊 Your weekly messages: {row[0] if row else 0}")

# ===== /top =====
async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("""
    SELECT s.count, u.username, u.first_name
    FROM stats s
    JOIN users u ON s.user_id = u.user_id
    WHERE s.chat_id=? AND s.year_week=?
    ORDER BY s.count DESC LIMIT 5
    """, (update.effective_chat.id, current_week()))

    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text("No activity yet.")
        return

    medals = ["🥇","🥈","🥉","🏅","🏅"]
    text = "🏆 Weekly Top Chatters 🏆\n\n"
    for i, (count, username, first_name) in enumerate(rows):
        name = f"@{username}" if username else first_name
        text += f"{medals[i]} {name} — {count}\n"
    await update.message.reply_text(text)

# ===== WELCOME =====
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    for user in update.message.new_chat_members:
        name = f"[{user.first_name}](tg://user?id={user.id})"
        text = (
            f"🎉 Welcome {name}!\n\n"
            "🐉 **Welcome to 索拉拉 SUOLALA CTO**\n"
            "💎 Stay strong. Stay patient."
        )

        try:
            if os.path.exists("welcome.gif"):
                with open("welcome.gif", "rb") as gif:
                    welcome_msg = await update.message.reply_animation(
                        animation=gif,
                        caption=text,
                        parse_mode="Markdown"
                    )
                    asyncio.create_task(delete_after_delay(welcome_msg, 300))
            else:
                welcome_msg = await update.message.reply_text(text, parse_mode="Markdown")
                asyncio.create_task(delete_after_delay(welcome_msg, 300))
        except Exception as e:
            welcome_msg = await update.message.reply_text(text, parse_mode="Markdown")
            asyncio.create_task(delete_after_delay(welcome_msg, 300))

# ===== GM / GN TASK =====
async def gm_gn_task(application):
    global LAST_GM_DATE, LAST_GN_DATE
    while True:
        now = datetime.now(CHINA_TZ)
        today = now.date()

        if 11 <= now.hour < 12 and LAST_GM_DATE != today:
            for cid in KNOWN_CHATS:
                try:
                    if os.path.exists("gm.gif"):
                        await application.bot.send_animation(cid, open("gm.gif", "rb"))
                except:
                    pass
            LAST_GM_DATE = today

        if 23 <= now.hour < 24 and LAST_GN_DATE != today:
            for cid in KNOWN_CHATS:
                try:
                    if os.path.exists("gn.gif"):
                        await application.bot.send_animation(cid, open("gn.gif", "rb"))
                except:
                    pass
            LAST_GN_DATE = today

        await asyncio.sleep(60)

async def randomnft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)

    try:
        headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0"
        }

        list_url = f"https://api-mainnet.magiceden.dev/v2/collections/{MAGICEDEN_COLLECTION}/listings?offset=0&limit=100"
        listings = requests.get(list_url, headers=headers, timeout=15).json()

        if not listings or not isinstance(listings, list):
            await update.message.reply_text("❌ No Suolala NFTs listed right now.")
            return

        nft = random.choice(listings)

        mint = nft.get("tokenMint")
        name = nft.get("title", "Suolala NFT")
        price = nft.get("price")

        if not mint or price is None:
            await update.message.reply_text("⚠️ NFT listing incomplete. Try again.")
            return

        token_url = f"https://api-mainnet.magiceden.dev/v2/tokens/{mint}"
        token_data = requests.get(token_url, headers=headers, timeout=15).json()
        image = token_data.get("image")

        if not image:
            await update.message.reply_text("⚠️ NFT image not found.")
            return

        buy_link = f"https://magiceden.io/item-details/{mint}"

        caption = (
            f"🎲 **Random Suolala NFT**\n\n"
            f"🖼 **{name}**\n"
            f"💰 **Price: {price:.4f} SOL**\n"
            f"🛒 Buy on Magic Eden\n"
            f"🔗 {buy_link}"
        )

        await update.message.reply_photo(
            photo=image,
            caption=caption,
            parse_mode="Markdown"
        )

    except Exception as e:
        print("RandomNFT ERROR:", e)
        await update.message.reply_text("⚠️ Failed to fetch NFT. Try again later.")

# ===== TEST BUY COMMAND =====
async def testbuy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test command to check if buy.png sends correctly"""
    remember_chat(update)
    
    test_caption = (
        "🚀 **TEST BUY ALERT** ✅\n\n"
        "💰 **Bought:** 102,917 SUOLALA\n"
        "💸 **Paid:** 0.197 SOL ≈ $197.96\n"
        "👤 **Buyer:** `0xe895...f924`\n"
        "🏷️ **Buyer Category:** 🐟 Fish ($100-$250)\n\n"
        "📊 **Price:** $0.001923\n"
        "🏦 **Market Cap:** $604,552.00\n"
        "📈 **24h Change:** +1.36%\n\n"
        "🔄 **TRADE $SUOLALA on Jupiter!**\n"
        "https://jup.ag/swap/SOL-CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )
    
    try:
        if os.path.exists("buy.png"):
            with open("buy.png", "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=test_caption,
                    parse_mode="Markdown"
                )
                await update.message.reply_text("✅ Test buy alert sent with buy.png!")
        else:
            await update.message.reply_text(
                "❌ buy.png not found! Place buy.png in the same directory as bot.py"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ===== BUY STATS COMMAND =====
async def buystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current pair stats"""
    remember_chat(update)
    
    try:
        response = requests.get(DEXSCREENER_PAIR_API, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            pair = data.get('pair', {})
            
            if pair:
                price_usd = float(pair.get('priceUsd', 0))
                market_cap = float(pair.get('marketCap', 0))
                liquidity_usd = float(pair.get('liquidity', {}).get('usd', 0))
                volume_h24 = float(pair.get('volume', {}).get('h24', 0))
                
                # Try to get transaction count
                tx_count = 0
                if 'txns' in pair and 'h24' in pair['txns']:
                    tx_count = len(pair['txns']['h24'].get('transactions', []))
                
                stats_text = (
                    "📊 **SUOLALA Pair Stats**\n\n"
                    f"💰 **Price:** ${price_usd:.6f}\n"
                    f"🏦 **Market Cap:** ${market_cap:,.2f}\n"
                    f"💧 **Liquidity:** ${liquidity_usd:,.2f}\n"
                    f"📈 **24h Volume:** ${volume_h24:,.2f}\n"
                    f"🔄 **24h Transactions:** {tx_count}\n\n"
                    f"🔗 **DexScreener:**\nhttps://dexscreener.com/solana/{PAIR_ADDRESS}\n\n"
                    "🔄 **Trade on Jupiter:**\nhttps://jup.ag/swap/SOL-CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
                )
                
                await update.message.reply_text(stats_text, parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Could not fetch pair data")
        else:
            await update.message.reply_text(f"❌ API Error: {response.status_code}")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ===== POST INITIALIZATION =====
async def post_init(app):
    # Start the GM/GN task
    app.create_task(gm_gn_task(app))
    # Start the buy monitoring task
    app.create_task(check_large_buys(app))
    print("✅ All background tasks started (GM/GN + Buy Alerts)")
    print(f"✅ Monitoring SUOLALA buys ≥ ${MIN_BUY_AMOUNT}")
    print(f"✅ Using Pair API: {DEXSCREENER_PAIR_API}")

# ===== START BOT =====
app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

# MESSAGE TRACKER MUST BE FIRST
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_messages))

# WELCOME
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

# TRANSLATER
app.add_handler(CommandHandler("translate", translate_cmd))

# ALL COMMANDS REGISTERED
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("price", price))
app.add_handler(CommandHandler("chart", chart))
app.add_handler(CommandHandler("buy", buy))
app.add_handler(CommandHandler("memes", memes))
app.add_handler(CommandHandler("stickers", stickers))
app.add_handler(CommandHandler("x", x))
app.add_handler(CommandHandler("community", community))
app.add_handler(CommandHandler("nft", nft))
app.add_handler(CommandHandler("contract", contract))
app.add_handler(CommandHandler("website", website))
app.add_handler(CommandHandler("rules", rules))
app.add_handler(CommandHandler("suolala", suolala))
app.add_handler(CommandHandler("motivate", motivate))
app.add_handler(CommandHandler("count", count_cmd))
app.add_handler(CommandHandler("top", top_cmd))
app.add_handler(CommandHandler("randomnft", randomnft))
app.add_handler(CommandHandler("testbuy", testbuy))
app.add_handler(CommandHandler("buystats", buystats))

print("=" * 50)
print("✅ SUOLALA BOT STARTING — ALL FEATURES ENABLED")
print(f"✅ Buy Monitoring: ≥ ${MIN_BUY_AMOUNT}")
print(f"✅ Contract: {SUOLALA_CONTRACT}")
print(f"✅ Pair Address: {PAIR_ADDRESS}")
print("=" * 50)
app.run_polling()
