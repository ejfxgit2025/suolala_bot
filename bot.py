import os
import random
import asyncio
import sqlite3
import requests
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

MAGICEDEN_COLLECTION = "suolala_"
MAGICEDEN_LIST_URL = "https://api-mainnet.magiceden.dev/v2/search?collection={}&status=listed&limit=100"

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

# ===== BASIC COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "🤖 SUOLALA Bot 🐉\n"
        "Official Solana China meme coin 🇨🇳🔥\n\n"
        "Commands:\n"
        "/price /chart /buy /memes /stickers\n"
        "/x /community /nft /contract /website /rules\n"
        "/suolala /motivate /count /top"
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
        "Static: https://t.me/addstickers/Suolala_cto\n"
        "Extra: https://t.me/addstickers/suolalastickers\n"
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

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    await update.message.reply_text(
        "📌 Rules\nNo spam | No scams | No fake links | Respect all"
    )

# ===== RANDOM IMAGE =====
async def suolala(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)
    IMAGE_DIR = "girls"
    img = random.choice([f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(("jpg","png","jpeg"))])
    await update.message.reply_photo(open(f"{IMAGE_DIR}/{img}", "rb"))

# ===== MOTIVATIONS (ALL 70) =====
MOTIVATIONS = [
    "🐉 SUOLALA is built by those who stay 💎",
    "💎 Holding SUOLALA means trusting your own vision 🔮",
    "🔥 Strong hands don’t look for exits — they build 🛡️",
    "🚀 SUOLALA moves when patience beats panic ⏳",
    "🧠 Calm minds protect SUOLALA better than hype 🧘",
    "💪 If holding was easy, everyone would own SUOLALA 🐉",
    "⏰ Time rewards SUOLALA believers 💎",
    "🌊 Noise fades. SUOLALA remains 🛡️",
    "🐲 SUOLALA doesn’t rush — it rises ⬆️",
    "📈 Price moves fast. Conviction lasts longer 🧠",
    "💎 Staying is harder than buying — that’s the edge ⚔️",
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
    "🚀 SUOLALA isn’t loud — it’s persistent ⏳",
    "🐲 Those who stay early shape what comes later 🔮",
    "📈 Growth rewards those who don’t rush it 🧘",
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
    "🐲 Those who wait patiently shape SUOLALA’s future 💎",
    "🐉 SUOLALA is built by patience, not pressure 💎",
    "💎 Those who believe early give SUOLALA its strength 🔥",
    "🚀 SUOLALA grows when holders stay focused ⏳",
    "🧠 Calm thinking keeps SUOLALA moving forward 🎯",
    "💪 SUOLALA rewards those who don’t rush 🛡️",
    "🔥 Real support is holding, not talking 🐉",
    "⏰ Time and belief shape SUOLALA together 💎",
    "🛡️ Strong holders protect SUOLALA’s future 🔒",
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
    "🐉 Those who stay patient shape SUOLALA’s path 💎",
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
            with open("welcome.gif", "rb") as gif:
                await update.message.reply_animation(
                    animation=gif,
                    caption=text,
                    parse_mode="Markdown"
                )
        except:
            await update.message.reply_text(text, parse_mode="Markdown")

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

async def post_init(app):
    app.create_task(gm_gn_task(app))

async def randomnft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_chat(update)

    try:
        url = MAGICEDEN_LIST_URL.format(MAGICEDEN_COLLECTION)

        headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        # Safety check
        if not isinstance(data, list) or len(data) == 0:
            await update.message.reply_text("❌ No Suolala NFTs listed right now.")
            return

        nft = random.choice(data)

        # Correct fields from Magic Eden
        name = nft.get("name", "Suolala NFT")
        price = nft.get("price", 0)
        mint = nft.get("mintAddress")
        image = nft.get("image")

        if not mint or not image:
            await update.message.reply_text("⚠️ NFT data incomplete. Try again.")
            return

        buy_link = f"https://magiceden.io/item-details/{mint}"

        caption = (
            f"🎲 **Random Listed NFT**\n\n"
            f"🖼 **{name}**\n"
            f"💰 **{price:.3f} SOL**\n"
            f"🛒 Buy on Magic Eden\n"
            f"🔗 {buy_link}"
        )

        await update.message.reply_photo(
            photo=image,
            caption=caption,
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text("⚠️ Failed to fetch NFT. Try again later.")



# ===== START BOT =====
app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

# MESSAGE TRACKER MUST BE FIRST
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_messages))

# WELCOME
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

# TRANSLATER
app.add_handler(CommandHandler("translate", translate_cmd))

# ALL COMMANDS REGISTERED (UNCHANGED)
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

print("✅ SUOLALA BOT RUNNING — ALL FEATURES ENABLED")
app.run_polling()




