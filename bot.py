
import os
import random
import asyncio
import sqlite3
import requests
import json
import time
from datetime import datetime
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

# ===== DEXSCREENER & ALERT CONFIG =====
SUOLALA_CONTRACT = "CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens/{}"
SOLSCAN_API = "https://public-api.solscan.io/account/transactions?account={}&limit=10"
JUPITER_API = "https://quote-api.jup.ag/v6/quote?inputMint=So11111111111111111111111111111111111111112&outputMint={}&amount=1000000000"

MIN_BUY_ALERT_USD = 100  # Minimum $ amount to trigger alert
ALERT_COOLDOWN = 60  # Seconds between checking for new buys
LAST_CHECKED_TIME_FILE = "last_checked.json"

# ===== BUYER CATEGORIES =====
BUYER_CATEGORIES = {
    (10, 250): "🐟 Fish",
    (250, 1000): "🦈 Shark",
    (1000, 5000): "🐬 Dolphin",
    (5000, 20000): "🦑 Kraken",
    (20000, float('inf')): "🐋 Whale"
}

# ===== MAGICEDEN NFT CONFIG =====
MAGICEDEN_COLLECTION = "suolala_"
MAGICEDEN_LIST_URL = "https://api-mainnet.magiceden.dev/v2/collections/{}/listings?offset=0&limit=100"

# ===== BOT TOKEN =====
TOKEN = os.getenv("BOT_TOKEN")

# ===== TIMEZONE =====
CHINA_TZ = ZoneInfo("Asia/Shanghai")

# ===== MEMORY (FIXED GM/GN) =====
KNOWN_CHATS_FILE = "known_chats.txt"
KNOWN_CHATS = set()
LAST_GM_DATE = None
LAST_GN_DATE = None
USED_MOTIVATIONS = {}

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
        pass  # Message might already be deleted or bot lacks permission

# ===== SAVE CHAT (FIXED) =====
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

# ===== BUY ALERT FEATURES =====
def get_buyer_category(usd_amount):
    for (min_val, max_val), category in BUYER_CATEGORIES.items():
        if min_val <= usd_amount < max_val:
            return f"{category} (${min_val}-${max_val})"
    return "🦐 Shrimp (<$10)"

async def fetch_token_data():
    """Fetch current token data from DexScreener"""
    try:
        response = requests.get(DEXSCREENER_API.format(SUOLALA_CONTRACT), timeout=10)
        data = response.json()
        
        if data.get('pairs'):
            pair = data['pairs'][0]
            
            token_info = {
                'price': float(pair.get('priceUsd', 0)),
                'price_native': float(pair.get('priceNative', 0)),
                'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                'market_cap': float(pair.get('fdv', 0)),
                'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                'dex_url': pair.get('url', ''),
                'pair_address': pair.get('pairAddress', '')
            }
            return token_info
    except Exception as e:
        print(f"Error fetching token data: {e}")
    return None

async def fetch_recent_transactions():
    """Fetch recent transactions for the token"""
    try:
        response = requests.get(SOLSCAN_API.format(SUOLALA_CONTRACT), timeout=10)
        data = response.json()
        
        transactions = []
        for tx in data.get('data', []):
            if tx.get('tokenTransfers'):
                for transfer in tx['tokenTransfers']:
                    if transfer.get('mint') == SUOLALA_CONTRACT:
                        transactions.append({
                            'signature': tx.get('txHash'),
                            'time': tx.get('blockTime'),
                            'from': transfer.get('from'),
                            'to': transfer.get('to'),
                            'amount': float(transfer.get('tokenAmount', {}).get('uiAmount', 0)),
                            'type': 'buy' if transfer.get('to') != SUOLALA_CONTRACT else 'sell'
                        })
        return transactions[-10:]  # Last 10 transactions
    except Exception as e:
        print(f"Error fetching transactions: {e}")
    return []

async def monitor_large_buys(application):
    """Background task to monitor for large purchases"""
    print("🔄 Starting Suolala buy monitor...")
    
    last_checked = {}
    if os.path.exists(LAST_CHECKED_TIME_FILE):
        with open(LAST_CHECKED_TIME_FILE, 'r') as f:
            last_checked = json.load(f)
    
    while True:
        try:
            # Get token data
            token_data = await fetch_token_data()
            if not token_data:
                await asyncio.sleep(ALERT_COOLDOWN)
                continue
            
            # Get recent transactions
            transactions = await fetch_recent_transactions()
            
            for tx in transactions:
                tx_time = tx['time']
                tx_key = tx['signature']
                
                # Skip if we've already processed this transaction
                if tx_key in last_checked:
                    continue
                
                # Calculate USD value
                usd_value = tx['amount'] * token_data['price']
                
                # Check if it's a buy and meets minimum threshold
                if tx['type'] == 'buy' and usd_value >= MIN_BUY_ALERT_USD:
                    # Prepare alert message
                    buyer_short = f"{tx['to'][:6]}...{tx['to'][-4:]}" if tx['to'] else "Unknown"
                    buyer_category = get_buyer_category(usd_value)
                    
                    alert_message = (
                        f"⚡ **SUOLALA / SOL BUY ALERT** ✅\n\n"
                        f"**Bought:** {tx['amount']:,.0f} SUOLALA\n"
                        f"**Paid:** {(tx['amount'] * token_data['price_native']):.3f} SOL ≈ ${usd_value:,.2f}\n"
                        f"**Buyer:** `{buyer_short}`\n"
                        f"**Buyer Category:** {buyer_category}\n\n"
                        f"**Price:** ${token_data['price']:.8f}\n"
                        f"**Market Cap:** ${token_data['market_cap']:,.2f}\n"
                        f"**24h Change:** {token_data['price_change_24h']:+.2f}%\n\n"
                        f"🔗 [Check on Solscan](https://solscan.io/tx/{tx['signature']})\n"
                        f"💱 [TRADE $SUOLALA on Jupiter](https://jup.ag/swap/SOL-{SUOLALA_CONTRACT})\n"
                    )
                    
                    # Send alert to all known chats WITH IMAGE
                    for chat_id in KNOWN_CHATS:
                        try:
                            # Try to send with buy.png image
                            if os.path.exists("buy.png"):
                                with open("buy.png", "rb") as photo:
                                    await application.bot.send_photo(
                                        chat_id=chat_id,
                                        photo=photo,
                                        caption=alert_message,
                                        parse_mode="Markdown"
                                    )
                            else:
                                # Fallback to text only if image not found
                                await application.bot.send_message(
                                    chat_id=chat_id,
                                    text=alert_message,
                                    parse_mode="Markdown",
                                    disable_web_page_preview=True
                                )
                            print(f"✅ Buy alert sent to chat {chat_id}")
                        except Exception as e:
                            print(f"Failed to send to chat {chat_id}: {e}")
                    
                    # Mark as processed
                    last_checked[tx_key] = tx_time
                    
                    # Save last checked times
                    with open(LAST_CHECKED_TIME_FILE, 'w') as f:
                        json.dump(last_checked, f)
                    
                    # Wait a bit between alerts to avoid rate limiting
                    await asyncio.sleep(2)
            
            # Clean old transactions (older than 1 hour)
            current_time = time.time()
            last_checked = {k: v for k, v in last_checked.items() 
                           if current_time - v < 3600}
            
        except Exception as e:
            print(f"Monitor error: {e}")
        
        await asyncio.sleep(ALERT_COOLDOWN)

async def pricecheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to check current token price and stats"""
    remember_chat(update)
    
    try:
        token_data = await fetch_token_data()
        if not token_data:
            await update.message.reply_text("❌ Could not fetch token data. Please try again.")
            return
        
        # Determine price trend emoji
        trend_emoji = "📈" if token_data['price_change_24h'] > 0 else "📉" if token_data['price_change_24h'] < 0 else "➡️"
        
        message = (
            f"💰 **SUOLALA Price Update** {trend_emoji}\n\n"
            f"**Current Price:** ${token_data['price']:.8f}\n"
            f"**Market Cap:** ${token_data['market_cap']:,.2f}\n"
            f"**24h Volume:** ${token_data['volume_24h']:,.2f}\n"
            f"**24h Change:** {token_data['price_change_24h']:+.2f}%\n"
            f"**Liquidity:** ${token_data['liquidity_usd']:,.2f}\n\n"
            f"🔗 [View Chart on DexScreener]({token_data['dex_url']})\n"
            f"💱 [Trade on Jupiter](https://jup.ag/swap/SOL-{SUOLALA_CONTRACT})"
        )
        
        sent = await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)
        
        # Auto-delete after 2 minutes
        asyncio.create_task(delete_after_delay(sent, 120))
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching price: {e}")

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
        "/translate /pricecheck\n\n"
        "⚡ **Auto Buy Alerts Enabled** - Large purchases (>$100) will be announced automatically with buy.png!"
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

    with open("nft.jpg", "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=caption
        )

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
            await update.message.reply_text("No images found in girls directory.")
    else:
        await update.message.reply_text("Girls directory not found.")

# ===== MOTIVATIONS (ALL 70) =====
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

# ===== WELCOME (FIXED WITH AUTO DELETE) =====
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
            with open("welcome.gif", "rb") as gif:
                welcome_msg = await update.message.reply_animation(
                    animation=gif,
                    caption=text,
                    parse_mode="Markdown"
                )
                # Schedule deletion after 5 minutes (300 seconds)
                asyncio.create_task(delete_after_delay(welcome_msg, 300))
        except Exception as e:
            # If GIF fails, send text only
            welcome_msg = await update.message.reply_text(text, parse_mode="Markdown")
            # Schedule deletion after 5 minutes
            asyncio.create_task(delete_after_delay(welcome_msg, 300))

# ===== GM / GN TASK (FIXED) =====
async def gm_gn_task(application):
    global LAST_GM_DATE, LAST_GN_DATE
    while True:
        now = datetime.now(CHINA_TZ)
        today = now.date()

        if 11 <= now.hour < 12 and LAST_GM_DATE != today:
            for cid in KNOWN_CHATS:
                try:
                    await application.bot.send_animation(cid, open("gm.gif", "rb"))
                except:
                    pass
            LAST_GM_DATE = today

        if 23 <= now.hour < 24 and LAST_GN_DATE != today:
            for cid in KNOWN_CHATS:
                try:
                    await application.bot.send_animation(cid, open("gn.gif", "rb"))
                except:
                    pass
            LAST_GN_DATE = today

        await asyncio.sleep(60)

def get_floor_price():
    try:
        url = f"https://api-mainnet.magiceden.dev/v2/collections/{MAGICEDEN_COLLECTION}/stats"
        headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0"
        }
        data = requests.get(url, headers=headers, timeout=10).json()
        floor_lamports = data.get("floorPrice", 0)
        if floor_lamports:
            return floor_lamports / 1_000_000_000
        return None
    except Exception as e:
        print("Floor price error:", e)
        return None

async def randomnft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)

    try:
        headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0"
        }

        # Fetch listed NFTs (REAL LISTINGS)
        list_url = f"https://api-mainnet.magiceden.dev/v2/collections/{MAGICEDEN_COLLECTION}/listings?offset=0&limit=100"
        listings = requests.get(list_url, headers=headers, timeout=15).json()

        if not listings or not isinstance(listings, list):
            await update.message.reply_text("❌ No Suolala NFTs listed right now.")
            return

        # Pick a random LISTED NFT
        nft = random.choice(listings)

        mint = nft.get("tokenMint")
        name = nft.get("title", "Suolala NFT")
        price = nft.get("price")

        if not mint or price is None:
            await update.message.reply_text("⚠️ NFT listing incomplete. Try again.")
            return

        # Fetch NFT metadata (image)
        token_url = f"https://api-mainnet.magiceden.dev/v2/tokens/{mint}"
        token_data = requests.get(token_url, headers=headers, timeout=15).json()
        image = token_data.get("image")

        if not image:
            await update.message.reply_text("⚠️ NFT image not found.")
            return

        # Buy link
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

# ===== POST INIT WITH ALL TASKS =====
async def post_init(app):
    """Start all background tasks"""
    app.create_task(gm_gn_task(app))
    app.create_task(monitor_large_buys(app))  # Add buy monitor
    print("✅ All background tasks started")

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
app.add_handler(CommandHandler("pricecheck", pricecheck))

print("✅ SUOLALA BOT RUNNING — ALL FEATURES ENABLED")
print("⚡ Buy Alert Monitor: ACTIVE (>$100 purchases will trigger alerts)")
print("🖼 Buy alerts will be sent WITH buy.png image")
print("🔄 Monitoring contract:", SUOLALA_CONTRACT)
app.run_polling()
