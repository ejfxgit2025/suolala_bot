import os
import random
from datetime import time
import pytz

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ===== BOT TOKEN =====
TOKEN = os.getenv("BOT_TOKEN")

# ===== CHAT STORAGE FILE =====
CHAT_FILE = "chats.txt"

# ===== SAVE CHAT ID (AUTO) =====
def save_chat_id(chat_id: int):
    if not os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "w") as f:
            f.write(str(chat_id) + "\n")
        return

    with open(CHAT_FILE, "r") as f:
        chats = f.read().splitlines()

    if str(chat_id) not in chats:
        with open(CHAT_FILE, "a") as f:
            f.write(str(chat_id) + "\n")

# ===== LOAD ALL CHATS =====
def load_chat_ids():
    if not os.path.exists(CHAT_FILE):
        return []
    with open(CHAT_FILE, "r") as f:
        return [int(x) for x in f.read().splitlines() if x.strip()]

# ===== QR HELPER (UNCHANGED) =====
async def send_qr_if_exists(update, name):
    path = f"qrcodes/{name}.jpg"
    if os.path.exists(path):
        await update.message.reply_photo(photo=open(path, "rb"))

# ===== BASIC COMMANDS (UNCHANGED, JUST SAVE CHAT) =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "🤖 SUOLALA Bot 🐉\n"
        "Official Solana China meme coin 🇨🇳🔥\n\n"
        "Commands:\n"
        "/price /chart /buy /memes /stickers\n"
        "/x /community /nft /contract /website /rules\n"
        "/suolala – Random Suolala Girl image"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "💰 SUOLALA Price\n"
        "https://dexscreener.com/solana/79Qaq5b1JfC8bFuXkAvXTR67fRPmMjMVNkEA3bb8bLzi"
    )
    await send_qr_if_exists(update, "price")

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "📈 SUOLALA Chart\n"
        "https://dexscreener.com/solana/79Qaq5b1JfC8bFuXkAvXTR67fRPmMjMVNkEA3bb8bLzi"
    )
    await send_qr_if_exists(update, "chart")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "🛒 How to Buy SUOLALA\n"
        "1️⃣ Create Phantom wallet\n"
        "2️⃣ Buy SOL\n"
        "3️⃣ Go to Jupiter \n"
        "4️⃣ Paste contract\n"
        "5️⃣ Swap SOL → SUOLALA\n\n"
        "🔥 Welcome to the dragon side"
    )
    await send_qr_if_exists(update, "buy")

async def memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text("😂 Memes\nhttps://t.me/suolala_memes")
    await send_qr_if_exists(update, "memes")

async def stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "🧧 Stickers\n"
        "Static: https://t.me/addstickers/Suolala_cto\n"
        "Extra: https://t.me/addstickers/suolalastickers\n"
        "Animated: https://t.me/addstickers/suolalaanimatedstickers"
    )

async def x(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text("🐦 X (Twitter)\nhttps://x.com/suolalax")
    await send_qr_if_exists(update, "x")

async def community(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "👥 Twitter Community\nhttps://twitter.com/i/communities/1980324795851186529"
    )
    await send_qr_if_exists(update, "community")

async def nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text("🖼️ NFTs coming soon 👀")

async def contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "📜 Contract Address\nCY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )
    await send_qr_if_exists(update, "contract")

async def website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "🌐 Website\nhttps://trends.fun/token/CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )
    await send_qr_if_exists(update, "website")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "📌 GROUP RULES\n"
        "1️⃣ No spam\n2️⃣ No scams\n3️⃣ No fake links\n4️⃣ Respect everyone"
    )

# ===== RANDOM IMAGE (UNCHANGED) =====
async def suolala(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    try:
        IMAGE_DIR = os.path.join(os.getcwd(), "girls")
        images = [i for i in os.listdir(IMAGE_DIR) if i.lower().endswith((".jpg", ".png", ".jpeg"))]
        image = random.choice(images)
        await update.message.reply_photo(
            photo=open(os.path.join(IMAGE_DIR, image), "rb"),
            caption="💜 We are 索拉拉 | SUOLALA 🔨"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ===== AUTO GM / GN (BROADCAST TO ALL CHATS) =====

CHINA_TZ = pytz.timezone("Asia/Shanghai")

async def send_gm(context):
    for chat_id in load_chat_ids():
        try:
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=open("gm.gif", "rb"),
                caption="🇨🇳 Good Morning ☀️"
            )
        except:
            pass

async def send_gn(context):
    for chat_id in load_chat_ids():
        try:
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=open("gn.gif", "rb"),
                caption="🇨🇳 Good Night 🌙"
            )
        except:
            pass

# ===== BOT SETUP =====

app = ApplicationBuilder().token(TOKEN).build()

# Schedule China time
app.job_queue.run_daily(send_gm, time=time(hour=9, minute=0, tzinfo=CHINA_TZ))
app.job_queue.run_daily(send_gn, time=time(hour=23, minute=0, tzinfo=CHINA_TZ))

# Handlers
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

print("✅ SUOLALA BOT RUNNING WITH GLOBAL GM/GN...")
app.run_polling()
