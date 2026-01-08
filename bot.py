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

    cur.execute("""
    INSERT INTO stats (user_id, chat_id, year_week, count)
    VALUES (?, ?, ?, 1)
    ON CONFLICT(user_id, chat_id, year_week)
    DO UPDATE SET count = count + 1
    """, (
        update.effective_user.id,
        update.effective_chat.id,
        current_week()
    ))
    db.commit()

# ================= /count =================
async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# ================= /top =================
async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("""
    SELECT user_id, count FROM stats
    WHERE chat_id=? AND year_week=?
    ORDER BY count DESC LIMIT 5
    """, (update.effective_chat.id, current_week()))
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("😴 No messages this week.")
        return

    medals = ["🥇", "🥈", "🥉", "🎖️", "🎖️"]
    text = "🏆 **Weekly Top Chatters** 🏆\n\n"

    for i, (uid, count) in enumerate(rows):
        try:
            user = await context.bot.get_chat(uid)
            name = f"@{user.username}" if user.username else user.first_name
        except:
            name = "Unknown"

        text += f"{medals[i]} {name} — **{count}** msgs\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ================= OLD COMMANDS (UNCHANGED) =================

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
    await update.message.reply_text("💰 SUOLALA Price")

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📈 SUOLALA Chart")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛒 How to Buy SUOLALA")

async def memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("😂 Memes")

async def stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧧 Stickers")

async def x(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🐦 X (Twitter)")

async def community(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 Community")

async def nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🖼️ NFTs coming soon")

async def contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📜 Contract Address")

async def website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌐 Website")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📌 Group Rules")

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

# 🔑 SAFE MESSAGE HANDLER (NO CRASH, NO LOOP)
app.add_handler(MessageHandler(~filters.COMMAND, track_messages))

# New commands
app.add_handler(CommandHandler("count", count_cmd))
app.add_handler(CommandHandler("top", top_cmd))

# Old commands
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

print("✅ SUOLALA BOT RUNNING — STABLE VERSION")
app.run_polling()
