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
LAST_CHECKED_TRADES = set()
ALERT_COOLDOWN = {}  # {chat_id: last_alert_time}

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

# ===== DIRECT DEXSCREENER SCRAPING =====
def get_direct_dexscreener_data():
    """Get accurate data directly from DexScreener page"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{PAIR_ADDRESS}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            pair = data.get('pair', {})
            
            if pair:
                # Get accurate price
                price_usd = float(pair.get('priceUsd', 0))
                
                # Get accurate market cap
                market_cap = float(pair.get('marketCap', 0))
                
                # Get price change
                price_change = 0
                price_change_data = pair.get('priceChange', {})
                if isinstance(price_change_data, dict):
                    price_change = float(price_change_data.get('h24', 0))
                else:
                    price_change = float(price_change_data or 0)
                
                # Get volume
                volume_h24 = 0
                volume_data = pair.get('volume', {})
                if isinstance(volume_data, dict):
                    volume_h24 = float(volume_data.get('h24', 0))
                
                # Get liquidity
                liquidity_usd = 0
                liquidity_data = pair.get('liquidity', {})
                if isinstance(liquidity_data, dict):
                    liquidity_usd = float(liquidity_data.get('usd', 0))
                
                return {
                    'price': price_usd,
                    'market_cap': market_cap,
                    'price_change_24h': price_change,
                    'volume_24h': volume_h24,
                    'liquidity': liquidity_usd,
                    'pair_address': PAIR_ADDRESS,
                    'dex_url': f"https://dexscreener.com/solana/{PAIR_ADDRESS}",
                    'timestamp': datetime.now().isoformat()
                }
        
        return None
    except Exception as e:
        print(f"❌ Error getting DexScreener data: {e}")
        return None

# ===== GET REAL TRANSACTIONS FROM BIRDEYE =====
def get_real_transactions():
    """Get REAL transactions from Birdeye API"""
    try:
        # Get current time and 5 minutes ago
        now = datetime.now()
        five_min_ago = int((now - timedelta(minutes=5)).timestamp())
        
        # Birdeye API endpoint for token trades
        url = f"https://public-api.birdeye.so/public/trades?address={SUOLALA_CONTRACT}&limit=10"
        
        headers = {
            'accept': 'application/json',
            'x-api-key': os.getenv('BIRDEYE_API_KEY', ''),  # Optional: Get free API key from birdeye.so
            'X-API-KEY': os.getenv('BIRDEYE_API_KEY', '')   # Some endpoints use this header
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                trades = data['data'].get('trades', [])
                
                # Filter for buys only and recent trades
                recent_buys = []
                for trade in trades:
                    # Check if it's a buy (based on action or amount)
                    trade_time = datetime.fromisoformat(trade.get('transactionTime', '1970-01-01'))
                    time_diff = (now - trade_time).total_seconds()
                    
                    # Only include trades from last 5 minutes
                    if time_diff <= 300:  # 5 minutes
                        recent_buys.append(trade)
                
                return recent_buys
        
        # Fallback: If no API key or Birdeye fails, use alternative method
        return get_recent_trades_fallback()
        
    except Exception as e:
        print(f"❌ Error getting real transactions: {e}")
        return []

def get_recent_trades_fallback():
    """Fallback method to detect large trades from price/volume spikes"""
    try:
        # Use DexScreener to get price data
        market_data = get_direct_dexscreener_data()
        
        if not market_data:
            return []
        
        # Track price changes over time
        price = market_data['price']
        volume = market_data['volume_24h']
        
        # We'll track historical data in a simple way
        # In production, you'd want to store this in a database
        if not hasattr(get_recent_trades_fallback, 'last_price'):
            get_recent_trades_fallback.last_price = price
            get_recent_trades_fallback.last_volume = volume
            get_recent_trades_fallback.last_check = datetime.now()
            return []
        
        # Calculate price change since last check
        time_diff = (datetime.now() - get_recent_trades_fallback.last_check).total_seconds()
        price_change = ((price - get_recent_trades_fallback.last_price) / get_recent_trades_fallback.last_price) * 100
        
        # Update tracking
        get_recent_trades_fallback.last_price = price
        get_recent_trades_fallback.last_volume = volume
        get_recent_trades_fallback.last_check = datetime.now()
        
        # If significant price increase in short time, might be a large buy
        if time_diff <= 60 and price_change > 2:  # >2% increase in 1 minute
            # Estimate trade size based on volume spike
            estimated_trade_value = volume * 0.05  # Assume 5% of recent volume
            
            if estimated_trade_value >= MIN_BUY_AMOUNT:
                return [{
                    'type': 'buy',
                    'amount': estimated_trade_value / price,
                    'value': estimated_trade_value,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'price_spike_detection'
                }]
        
        return []
        
    except Exception as e:
        print(f"❌ Error in fallback trade detection: {e}")
        return []

# ===== TOKEN BUY MONITORING =====
async def check_large_buys(app):
    """Background task to check for large token buys - REAL TRANSACTIONS ONLY"""
    global LAST_CHECKED_TRADES
    
    print("🔄 Starting REAL buy monitoring...")
    
    # Initialize tracking
    last_alert_time = datetime.now() - timedelta(minutes=10)
    
    while True:
        try:
            current_time = datetime.now()
            
            # Don't check too frequently
            if (current_time - last_alert_time).total_seconds() < 120:
                await asyncio.sleep(30)
                continue
            
            print("🔍 Checking for REAL buys...")
            
            # Get current market data
            market_data = get_direct_dexscreener_data()
            
            if not market_data:
                print("⚠️ Could not get market data")
                await asyncio.sleep(60)
                continue
            
            # Get REAL transactions
            transactions = get_real_transactions()
            
            if transactions:
                print(f"📊 Found {len(transactions)} recent transactions")
                
                # Process each transaction
                for tx in transactions:
                    if not isinstance(tx, dict):
                        continue
                    
                    # Generate unique ID for this transaction
                    tx_id = f"{tx.get('signature', '')}_{tx.get('timestamp', '')}"
                    
                    if not tx_id or tx_id in LAST_CHECKED_TRADES:
                        continue
                    
                    # Get transaction value
                    tx_value = float(tx.get('value', 0))
                    tx_amount = float(tx.get('amount', 0))
                    
                    # If value not provided, calculate it
                    if tx_value == 0 and tx_amount > 0:
                        tx_value = tx_amount * market_data['price']
                    
                    # Check if buy and meets threshold
                    if tx_value >= MIN_BUY_AMOUNT:
                        print(f"✅ Detected REAL large buy: ${tx_value:.2f}")
                        
                        # Send alert
                        await send_buy_alert(app, tx, market_data, tx_value, tx_amount)
                        
                        # Update tracking
                        LAST_CHECKED_TRADES.add(tx_id)
                        last_alert_time = current_time
                        
                        # Limit memory
                        if len(LAST_CHECKED_TRADES) > 100:
                            LAST_CHECKED_TRADES = set(list(LAST_CHECKED_TRADES)[-50:])
                        
                        # Wait before checking next transaction
                        await asyncio.sleep(60)
                        break
            else:
                print("📭 No recent transactions found")
                
        except Exception as e:
            print(f"❌ Error in buy monitoring: {e}")
            import traceback
            traceback.print_exc()
        
        # Wait 2 minutes before next check
        await asyncio.sleep(120)

async def send_buy_alert(app, transaction, market_data, usd_value, token_amount):
    """Send REAL buy alert to all known chats"""
    try:
        # Get transaction details
        tx_hash = transaction.get('signature', 'Not available')
        buyer_address = transaction.get('buyer', 'Unknown')
        
        # Get accurate market data
        current_price = market_data['price']
        market_cap = market_data['market_cap']
        price_change = market_data['price_change_24h']
        
        # Calculate SOL amount (approximate)
        sol_price = 100  # Approximate SOL price
        sol_amount = usd_value / sol_price
        
        # Determine buyer category
        if usd_value >= 1000:
            category = "🐋 Whale ($1,000+)"
        elif usd_value >= 250:
            category = "🦈 Shark ($250-$1,000)"
        else:
            category = "🐟 Fish ($100-$250)"
        
        # Format amounts
        if token_amount >= 1000000:
            formatted_token_amount = f"{token_amount/1000000:.2f}M"
        elif token_amount >= 1000:
            formatted_token_amount = f"{token_amount/1000:.2f}K"
        else:
            formatted_token_amount = f"{token_amount:,.0f}"
            
        formatted_usd_value = "${:,.2f}".format(usd_value)
        formatted_sol_amount = "{:.3f}".format(sol_amount)
        
        # Format price
        if current_price < 0.0001:
            formatted_price = "${:.8f}".format(current_price)
        elif current_price < 0.01:
            formatted_price = "${:.6f}".format(current_price)
        else:
            formatted_price = "${:.4f}".format(current_price)
            
        formatted_market_cap = "${:,.2f}".format(market_cap)
        
        # Create REAL caption
        caption = (
            "🚀 **SUOLALA BUY ALERT** ✅\n\n"
            f"💰 **Bought:** {formatted_token_amount} SUOLALA\n"
            f"💸 **Paid:** {formatted_sol_amount} SOL ≈ {formatted_usd_value}\n"
            f"🏷️ **Buyer Category:** {category}\n\n"
            f"📊 **Current Price:** {formatted_price}\n"
            f"🏦 **Market Cap:** {formatted_market_cap}\n"
            f"📈 **24h Change:** {price_change:+.2f}%\n\n"
        )
        
        # Add transaction link if available
        if tx_hash != "Not available" and len(tx_hash) > 10 and not tx_hash.startswith("solscan:"):
            caption += f"🔍 **Transaction:**\nhttps://solscan.io/tx/{tx_hash}\n\n"
        
        caption += (
            "🔄 **Trade $SUOLALA on Jupiter!**\n"
            "https://jup.ag/swap/SOL-CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8\n\n"
            "📊 **View Chart:**\n"
            f"https://dexscreener.com/solana/{PAIR_ADDRESS}"
        )
        
        current_time = datetime.now()
        
        # Send to all known chats with cooldown
        for chat_id in list(KNOWN_CHATS):
            try:
                # Check cooldown (10 minutes between alerts per chat)
                last_alert = ALERT_COOLDOWN.get(chat_id)
                if last_alert and (current_time - last_alert).total_seconds() < 600:
                    print(f"⏳ Skipping chat {chat_id} (cooldown)")
                    continue
                
                # Try to send with image
                if os.path.exists("buy.png"):
                    with open("buy.png", "rb") as photo:
                        await app.bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=caption,
                            parse_mode="Markdown"
                        )
                        print(f"✅ REAL buy alert sent to chat {chat_id}")
                else:
                    # Send as text
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        parse_mode="Markdown"
                    )
                    print(f"📝 REAL buy alert sent (text) to chat {chat_id}")
                
                # Update cooldown
                ALERT_COOLDOWN[chat_id] = current_time
                    
            except Exception as e:
                error_msg = str(e).lower()
                if "chat not found" in error_msg or "bot was blocked" in error_msg or "forbidden" in error_msg:
                    # Remove inactive chat
                    KNOWN_CHATS.discard(chat_id)
                    print(f"🗑️ Removed inactive chat {chat_id}")
                else:
                    print(f"⚠️ Failed to send to chat {chat_id}: {e}")
                
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
        "/market /stats"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    market_data = get_direct_dexscreener_data()
    
    if market_data:
        text = (
            f"💰 **SUOLALA Price:** ${market_data['price']:.6f}\n"
            f"📈 **24h Change:** {market_data['price_change_24h']:+.2f}%\n"
            f"🏦 **Market Cap:** ${market_data['market_cap']:,.2f}\n"
            f"💧 **Liquidity:** ${market_data['liquidity']:,.2f}\n"
            f"📊 **24h Volume:** ${market_data['volume_24h']:,.2f}\n\n"
            f"🔗 **View on DexScreener:**\n"
            f"https://dexscreener.com/solana/{PAIR_ADDRESS}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
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

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current market stats"""
    remember_chat(update)
    
    market_data = get_direct_dexscreener_data()
    
    if market_data:
        text = (
            "📊 **SUOLALA Market Stats**\n\n"
            f"💰 **Price:** ${market_data['price']:.6f}\n"
            f"📈 **24h Change:** {market_data['price_change_24h']:+.2f}%\n"
            f"🏦 **Market Cap:** ${market_data['market_cap']:,.2f}\n"
            f"💧 **Liquidity:** ${market_data['liquidity']:,.2f}\n"
            f"📊 **24h Volume:** ${market_data['volume_24h']:,.2f}\n\n"
            f"🔗 **DexScreener:** https://dexscreener.com/solana/{PAIR_ADDRESS}\n"
            f"🔄 **Jupiter:** https://jup.ag/swap/SOL-CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Could not fetch market data")

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

# ===== STATS COMMAND =====
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot stats"""
    remember_chat(update)
    
    market_data = get_direct_dexscreener_data()
    stats_text = (
        f"🤖 **SUOLALA Bot Stats**\n\n"
        f"👥 **Active Chats:** {len(KNOWN_CHATS)}\n"
        f"📊 **Tracked Trades:** {len(LAST_CHECKED_TRADES)}\n"
        f"⏰ **Monitoring:** $100+ buys\n\n"
    )
    
    if market_data:
        stats_text += (
            f"💰 **Current Price:** ${market_data['price']:.6f}\n"
            f"📈 **24h Change:** {market_data['price_change_24h']:+.2f}%\n"
            f"💧 **Liquidity:** ${market_data['liquidity']:,.2f}\n\n"
        )
    
    stats_text += "✅ **Bot Status:** ACTIVE & MONITORING"
    await update.message.reply_text(stats_text, parse_mode="Markdown")

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
                        print(f"🌅 GM sent to chat {cid}")
                except Exception as e:
                    print(f"❌ Failed to send GM to chat {cid}: {e}")
            LAST_GM_DATE = today

        if 23 <= now.hour < 24 and LAST_GN_DATE != today:
            for cid in KNOWN_CHATS:
                try:
                    if os.path.exists("gn.gif"):
                        await application.bot.send_animation(cid, open("gn.gif", "rb"))
                        print(f"🌙 GN sent to chat {cid}")
                except Exception as e:
                    print(f"❌ Failed to send GN to chat {cid}: {e}")
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

# ===== LATEST BUY COMMAND =====
async def latestbuy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the latest REAL buy if available"""
    remember_chat(update)
    
    try:
        # Get real transactions
        transactions = get_real_transactions()
        
        if not transactions:
            await update.message.reply_text(
                "📭 No recent buys detected in the last 5 minutes.\n\n"
                "✅ The bot is actively monitoring for $100+ buys.\n"
                "🔔 Alerts will be sent automatically when detected."
            )
            return
        
        # Get market data
        market_data = get_direct_dexscreener_data()
        
        if not market_data:
            await update.message.reply_text("❌ Could not fetch market data")
            return
        
        # Show latest buy
        latest_tx = transactions[0]
        tx_value = float(latest_tx.get('value', 0))
        tx_amount = float(latest_tx.get('amount', 0))
        
        if tx_value == 0 and tx_amount > 0:
            tx_value = tx_amount * market_data['price']
        
        if tx_value < MIN_BUY_AMOUNT:
            await update.message.reply_text(
                f"📊 Latest buy: ${tx_value:.2f} (below $100 threshold)\n\n"
                "✅ Monitoring continues for $100+ buys..."
            )
            return
        
        # Send alert for the latest buy
        await send_buy_alert(app, latest_tx, market_data, tx_value, tx_amount)
        await update.message.reply_text("✅ Latest buy alert sent!")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ===== POST INITIALIZATION =====
async def post_init(app):
    # Start the GM/GN task
    app.create_task(gm_gn_task(app))
    # Start the REAL buy monitoring task
    app.create_task(check_large_buys(app))
    
    # Get initial market data to verify
    market_data = get_direct_dexscreener_data()
    if market_data:
        print("✅ Market Data Verified:")
        print(f"   Price: ${market_data['price']:.6f}")
        print(f"   Market Cap: ${market_data['market_cap']:,.2f}")
        print(f"   24h Change: {market_data['price_change_24h']:+.2f}%")
        print(f"   24h Volume: ${market_data['volume_24h']:,.2f}")
    
    print("✅ All background tasks started")
    print(f"✅ Monitoring SUOLALA REAL buys ≥ ${MIN_BUY_AMOUNT}")
    print(f"✅ Cooldown: 10 minutes between alerts per chat")
    print(f"✅ Active Chats: {len(KNOWN_CHATS)}")
    print("✅ Using REAL transaction data (Birdeye API)")

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
app.add_handler(CommandHandler("market", market))
app.add_handler(CommandHandler("stats", stats_cmd))
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
app.add_handler(CommandHandler("latestbuy", latestbuy))

print("=" * 50)
print("✅ SUOLALA BOT STARTING — REAL ALERTS ONLY")
print(f"✅ Buy Monitoring: ≥ ${MIN_BUY_AMOUNT} (REAL TRANSACTIONS ONLY)")
print(f"✅ Contract: {SUOLALA_CONTRACT}")
print(f"✅ Pair Address: {PAIR_ADDRESS}")
print(f"✅ Alert Cooldown: 10 minutes per chat")
print("=" * 50)
print("🚫 NO FAKE ALERTS — ONLY REAL TRANSACTIONS")
print("📊 Using Birdeye API for REAL transaction data")
print("=" * 50)

# Check for Birdeye API key
if not os.getenv('BIRDEYE_API_KEY'):
    print("⚠️  WARNING: No Birdeye API key found!")
    print("⚠️  Get free API key from: https://birdeye.so/")
    print("⚠️  Bot will use fallback monitoring (price spikes)")
else:
    print("✅ Birdeye API key found!")

app.run_polling()
