import os
import random
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
CHINA_TZ = ZoneInfo("Asia/Shanghai")

KNOWN_CHATS = set()
LAST_GM_DATE = None
LAST_GN_DATE = None

# ================= HELPERS =================

def remember_chat(update: Update):
    if update and update.effective_chat:
        KNOWN_CHATS.add(update.effective_chat.id)

async def send_qr_if_exists(update, name):
    path = f"qrcodes/{name}.jpg"
    if os.path.exists(path):
        await update.message.reply_photo(photo=open(path, "rb"))

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "🤖 SUOLALA Bot 🐉\n"
        "Official Solana China meme coin 🇨🇳🔥\n\n"
        "Commands:\n"
        "/price /chart /buy /memes /stickers\n"
        "/x /community /nft /contract /website /rules\n"
        "/suolala – Random Suolala Girl image"
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
    await update.message.reply_text(
        "🛒 How to Buy SUOLALA\n"
        "1️⃣ Create Phantom wallet\n"
        "2️⃣ Buy SOL\n"
        "3️⃣ Go to Jupiter\n"
        "4️⃣ Paste contract\n"
        "5️⃣ Swap SOL → SUOLALA\n\n"
        "🔥 Welcome to the dragon side"
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
        "Static: https://t.me/addstickers/Suolala_cto\n"
        "Extra: https://t.me/addstickers/suolalastickers\n"
        "Animated: https://t.me/addstickers/suolalaanimatedstickers"
    )

async def x(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text("🐦 X (Twitter)\nhttps://x.com/suolalax")
    await send_qr_if_exists(update, "x")

async def community(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "👥 Twitter Community\n"
        "https://twitter.com/i/communities/1980324795851186529"
    )
    await send_qr_if_exists(update, "community")

async def nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text("🖼️ NFTs coming soon 👀")

async def contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "📜 Contract Address\n"
        "CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )
    await send_qr_if_exists(update, "contract")

async def website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "🌐 Website\n"
        "https://trends.fun/token/CY1P83KnKwFYostvjQcoR2HJLyEJWRBRaVQmYyyD3cR8"
    )
    await send_qr_if_exists(update, "website")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "📌 GROUP RULES\n"
        "1️⃣ No spam\n"
        "2️⃣ No scams\n"
        "3️⃣ No fake links\n"
        "4️⃣ Respect everyone\n"
        "Violators will be banned 🚫"
    )

async def suolala(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    IMAGE_DIR = "girls"
    image = random.choice([
        f for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith((".jpg", ".png", ".jpeg"))
    ])
    await update.message.reply_photo(
        photo=open(os.path.join(IMAGE_DIR, image), "rb"),
        caption="💜 We are 索拉拉 | SUOLALA 🔨"
    )

# ================= GM / GN BACKGROUND TASK =================

async def gm_gn_task(application):
    global LAST_GM_DATE, LAST_GN_DATE

    while True:
        now = datetime.now(CHINA_TZ)
        today = now.date()

        # ===== GM (10:30 China = 08:00 Sri Lanka) =====
        if now.hour == 10 and now.minute == 30 and LAST_GM_DATE != today:
            for chat_id in KNOWN_CHATS:
                try:
                    await application.bot.send_animation(
                        chat_id=chat_id,
                        animation=open("gm.gif", "rb"),
                        caption="🌅 **Good Morning, SUOLALA Family!**\n\n"
                                "🐉 Wake up strong, stay bullish 💎\n"
                                "🇨🇳 索拉拉与你同在 ☀️🔥"
                    )
                except:
                    try:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text="🌅 **Good Morning, SUOLALA Family!**\n\n"
                                 "🐉 Wake up strong, stay bullish 💎\n"
                                 "🇨🇳 索拉拉与你同在 ☀️🔥",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

            LAST_GM_DATE = today

        # ===== GN (23:00 China = 20:30 Sri Lanka) =====
        if now.hour == 23 and LAST_GN_DATE != today:
            for chat_id in KNOWN_CHATS:
                try:
                    await application.bot.send_animation(
                        chat_id=chat_id,
                        animation=open("gn.gif", "rb"),
                        caption="🌙 **Good Night, SUOLALA Family!**\n\n"
                                "🐉 Rest well, tomorrow we rise 🚀\n"
                                "🇨🇳 索拉拉晚安 🌙💜"
                    )
                except:
                    try:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text="🌙 **Good Night, SUOLALA Family!**\n\n"
                                 "🐉 Rest well, tomorrow we rise 🚀\n"
                                 "🇨🇳 索拉拉晚安 🌙💜",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

            LAST_GN_DATE = today

        await asyncio.sleep(60)

# ================= START BOT =================

app = (
    ApplicationBuilder()
    .token(TOKEN)
    .post_init(post_init)
    .build()
)

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

print("✅ SUOLALA BOT RUNNING (STABLE, NO CRASH)")
app.run_polling()


