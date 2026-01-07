from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8347438538:AAFtei8ytovk_s1SoxerKlQASsNHwprs6y8"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Welcome to SUOLALA 🐉\n\n"
        "The official Solana-based China meme coin 🇨🇳🔥\n\n"
        "Commands:\n"
        "/price – Live price\n"
        "/chart – Dex chart\n"
        "/buy – How to buy\n"
        "/memes – Meme channel\n"
        "/stickers – Sticker packs\n"
        "/x – Twitter (X)\n"
        "/community – Twitter Community\n"
        "/nft – NFT info\n"
        "/contract – Contract address\n"
        "/website – Website\n"
        "/rules – Group rules"
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
        "3️⃣ Open Jupiter / Dexscreener\n"
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
        "5️⃣ English only\n\n"
        "Violators will be banned 🚫"
    )

app = ApplicationBuilder().token(TOKEN).build()

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

print("✅ SUOLALA BOT RUNNING...")
app.run_polling()
