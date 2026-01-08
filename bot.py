import os
import random
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ===== BOT TOKEN =====
TOKEN = os.getenv("BOT_TOKEN")

# ===== DATABASE =====
db = sqlite3.connect("msg_stats.db", check_same_thread=False)
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
db.commit()

# ===== HELPER: CURRENT WEEK =====
def current_year_week():
    year, week, _ = datetime.utcnow().isocalendar()
    return f"{year}-W{week:02d}"

# ===== BASIC COMMANDS (UNCHANGED) =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 SUOLALA Bot 🐉\n"
        "Official Solana China meme coin 🇨🇳🔥\n\n"
        "Commands:\n"
        "/price /chart /buy /memes /stickers\n"
        "/x /community /nft /contract /website /rules\n"
        "/suolala – Random Suolala Girl image\n"
        "/count – Your weekly chat stats\n"
        "/top – Weekly top chatters 🏆"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 SUOLALA Price\n"
        "https://dexscreener.com/solana/79Qaq5b1JfC8bFuXkAvXTR67fRPmMjMVNkEA3bb8bLzi"
    )

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 SUOLALA Chart\n"
        "https://dexscreener.com/solana/79Qaq5b1JfC8bFuXkAvXTR67fRPmMjMVNkEA3bb8bLzi"
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛒 How to Buy SUOLALA\n"
        "1️⃣ Create Phantom wallet\n"
        "2️⃣ Buy SOL\n"
        "3️⃣ Go to Jupiter \n"
        "4️⃣ Paste contract\n"
        "5️⃣ Swap SOL → SUOLALA\n\n"
        "🔥 Welcome to the dragon side"
    )

async def memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("😂 Memes\nhttps://t.me/suolala_memes")

async def stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧧 Stickers\n"
        "Static: https://t.me/addstickers/Suolala_cto\n"
        "Extra: https://t.me/addstickers/suolalastickers\n"
        "Animated: https://t.me/addstickers/suolalaanimatedstickers"
    )

async def x(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🐦 X (Twitter)\nhttps://x.com/suolalax")

async def community(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👥 Twitter Community\n"
        "https://twitter.com/i/communities/1980324795851186529"
    )

async def nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🖼️ NFTs coming soon 👀")

async def contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 Contract Address\n"
        "CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )

async def website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Website\n"
        "https://trends.fun/token/CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 GROUP RULES\n"
        "1️⃣ No spam\n"
        "2️⃣ No scams\n"
        "3️⃣ No fake links\n"
        "4️⃣ Respect everyone\n"
        "Violators will be banned 🚫"
    )

# ===== SUOLALA IMAGE =====

async def suolala(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        IMAGE_DIR = os.path.join(os.getcwd(), "girls")
        images = [i for i in os.listdir(IMAGE_DIR) if i.lower().endswith(("jpg", "png", "jpeg"))]
        image = random.choice(images)

        await update.message.reply_photo(
            photo=open(os.path.join(IMAGE_DIR, image), "rb"),
            caption="💜 We are 索拉拉 | SUOLALA 🔨"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ===== MESSAGE TRACKER (WEEKLY) =====

async def track_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.type == "private":
        return

    yw = current_year_week()
    uid = update.effective_user.id
    cid = update.effective_chat.id

    cur.execute("""
    INSERT INTO stats VALUES (?, ?, ?, 1)
    ON CONFLICT(user_id, chat_id, year_week)
    DO UPDATE SET count = count + 1
    """, (uid, cid, yw))
    db.commit()

# ===== /count (WEEKLY) =====

async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    yw = current_year_week()
    uid = update.effective_user.id
    cid = update.effective_chat.id

    cur.execute(
        "SELECT count FROM stats WHERE user_id=? AND chat_id=? AND year_week=?",
        (uid, cid, yw)
    )
    row = cur.fetchone()
    total = row[0] if row else 0

    await update.message.reply_text(
        f"📊 **Your Weekly SUOLALA Stats**\n\n"
        f"🗓 Week: `{yw}`\n"
        f"💬 Messages: **{total}**\n\n"
        f"🐉 Keep grinding, dragon!",
        parse_mode="Markdown"
    )

# ===== /top (WEEKLY + USERNAME) =====

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    yw = current_year_week()
    cid = update.effective_chat.id

    cur.execute("""
    SELECT user_id, count FROM stats
    WHERE chat_id=? AND year_week=?
    ORDER BY count DESC LIMIT 5
    """, (cid, yw))

    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text("😴 No chat activity this week yet.")
        return

    text = "🏆 **Top SUOLALA Chatters (This Week)** 🏆\n\n"
    medals = ["🥇", "🥈", "🥉", "🎖️", "🎖️"]

    for i, (uid, count) in enumerate(rows):
        try:
            user = await context.bot.get_chat(uid)
            name = f"@{user.username}" if user.username else user.first_name
        except:
            name = "Unknown"

        text += f"{medals[i]} {name} — **{count}** msgs\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ===== BOT SETUP =====

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_messages))
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
app.add_handler(CommandHandler("count", count_cmd))
app.add_handler(CommandHandler("top", top_cmd))

print("✅ SUOLALA BOT RUNNING (WEEKLY MODE)...")
app.run_polling()
