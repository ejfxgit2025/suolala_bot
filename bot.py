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

# ================= BOT TOKEN =================
TOKEN = os.getenv("BOT_TOKEN")

# ================= DATABASE ==================
db = sqlite3.connect("weekly_stats.db", check_same_thread=False)
cur = db.cursor()

# message stats
cur.execute("""
CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER,
    chat_id INTEGER,
    year_week TEXT,
    count INTEGER,
    PRIMARY KEY (user_id, chat_id, year_week)
)
""")

# user cache (KEY FIX)
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

# ================= MESSAGE TRACKER =================
async def track_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if update.message.from_user.is_bot:
        return
    if update.effective_chat.type == "private":
        return

    user = update.effective_user

    # save user info (NO Telegram API call)
    cur.execute("""
    INSERT INTO users (user_id, username, first_name)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id)
    DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name
    """, (user.id, user.username, user.first_name))

    # save stats
    cur.execute("""
    INSERT INTO stats (user_id, chat_id, year_week, count)
    VALUES (?, ?, ?, 1)
    ON CONFLICT(user_id, chat_id, year_week)
    DO UPDATE SET count = count + 1
    """, (user.id, update.effective_chat.id, current_week()))

    db.commit()

# ================= /count =================
async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("This command only works in group chats.")
        return

    cur.execute(
        "SELECT count FROM stats WHERE user_id=? AND chat_id=? AND year_week=?",
        (update.effective_user.id, update.effective_chat.id, current_week())
    )
    row = cur.fetchone()
    total = row[0] if row else 0

    await update.message.reply_text(
        f"📊 **Weekly SUOLALA Stats**\n\n"
        f"🗓 Week: `{current_week()}`\n"
        f"💬 Messages: **{total}**",
        parse_mode="Markdown"
    )

# ================= /top (WORKS IN ALL GROUPS) =================
async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("This command only works in group chats.")
        return

    cur.execute("""
    SELECT s.count, u.username, u.first_name
    FROM stats s
    JOIN users u ON s.user_id = u.user_id
    WHERE s.chat_id=? AND s.year_week=?
    ORDER BY s.count DESC
    LIMIT 5
    """, (update.effective_chat.id, current_week()))

    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text("😴 No messages this week yet.")
        return

    medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
    text = "🏆 **Weekly Top Chatters** 🏆\n\n"

    for i, (count, username, first_name) in enumerate(rows):
        name = f"@{username}" if username else (first_name or "Unknown")
        text += f"{medals[i]} {name} — **{count}** msgs\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ================= ORIGINAL COMMANDS (WITH LINKS) =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 SUOLALA Bot 🐉\n"
        "Official Solana China meme coin 🇨🇳🔥\n\n"
        "Commands:\n"
        "/price /chart /buy /memes /stickers\n"
        "/x /community /nft /contract /website /rules\n"
        "/suolala – Random Suolala Girl image\n"
        "/count – Weekly chat count\n"
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
        "1️⃣ Create Phantom Wallet\n"
        "2️⃣ Buy SOL\n"
        "3️⃣ Go to Jupiter\n"
        "4️⃣ Paste Contract Address\n"
        "5️⃣ Swap SOL → SUOLALA\n\n"
        "🔗 https://jup.ag"
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

async def suolala(update: Update, context: ContextTypes.DEFAULT_TYPE):
    IMAGE_DIR = os.path.join(os.getcwd(), "girls")
    images = [i for i in os.listdir(IMAGE_DIR) if i.lower().endswith(("jpg","png","jpeg"))]
    image = random.choice(images)
    await update.message.reply_photo(
        photo=open(os.path.join(IMAGE_DIR, image), "rb"),
        caption="💜 We are 索拉拉 | SUOLALA 🔨"
    )

# ================= BOT SETUP =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_messages))
app.add_handler(CommandHandler("count", count_cmd))
app.add_handler(CommandHandler("top", top_cmd))
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

print("✅ SUOLALA BOT RUNNING — FINAL STABLE VERSION")
app.run_polling()
