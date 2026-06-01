from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import psycopg2
import os
import time
import threading
import uuid
import os

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

ADMINS = [8196100632, 5418159522]

PUBLIC_CHANNEL = "@zapaskaktos1"
PRIVATE_CHANNEL_LINK = "https://t.me/+9b5xs_0PeBBmZTg0"
POST_CHANNEL = -1003939035699

BOT_USERNAME = "Aploderkaktos_bot"

DELETE_TIME = 30

# ================= DB (AUTO RECONNECT) =================


def connect_db():
    while True:
        try:
            conn = psycopg2.connect(
                os.environ.get("DATABASE_URL"),
                connect_timeout=5
            )
            cursor = conn.cursor()
            print("✅ Database Connected")
            return conn, cursor
        except Exception as e:
            print("❌ DB Error:", e)
            time.sleep(5)


def ensure_connection():
    global conn, cursor
    try:
        cursor.execute("SELECT 1")
    except:
        print("🔄 Reconnecting DB...")
        conn, cursor = connect_db()


# ================= CREATE TABLE =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
id BIGINT PRIMARY KEY
)
""")
conn.commit()
ensure_connection()
cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
name TEXT PRIMARY KEY,
file_id TEXT
)
""")
conn.commit()

# ================= JOIN CHECK =================


def is_joined(user_id):

    try:
        member = bot.get_chat_member(PUBLIC_CHANNEL, user_id)
        return member.status not in ["left", "kicked"]
    except:
        return False

# ================= DB FUNCTIONS =================


def save_movie(name, file_id):

    ensure_connection()


cursor.execute(
    "INSERT INTO movies (name, file_id) VALUES (%s,%s) ON CONFLICT (name) DO UPDATE SET file_id = EXCLUDED.file_id",
    (name, file_id)
)
conn.commit()


def get_movie(name):

    ensure_connection()


cursor.execute("SELECT file_id FROM movies WHERE name=%s", (name,))
result = cursor.fetchone()
return result[0] if result else None


def delete_movie_db(name):

    ensure_connection()


cursor.execute("DELETE FROM movies WHERE name=%s", (name,))
conn.commit()

# ================= ADMIN STATE =================
waiting = {}


@bot.message_handler(commands=['add'])
def add_movie(message):

    if message.from_user.id not in ADMINS:
        return


data = message.text.split()
if len(data) < 2:
    bot.reply_to(message, "/add name")
return

waiting[message.from_user.id] = {"name": data[1]}
bot.reply_to(message, "📸 عکس بفرست")


@bot.message_handler(content_types=['photo'])
def photo(message):

    if message.from_user.id not in waiting:
        return


waiting[message.from_user.id]["photo"] = message.photo[-1].file_id
bot.reply_to(message, "🎬 ویدیو بفرست")


@bot.message_handler(content_types=['video'])
def video(message):

    if message.from_user.id not in waiting:
        return


data = waiting[message.from_user.id]

if "photo" not in data:
    bot.reply_to(message, "❌ اول عکس")
return

name = data["name"]  # فقط برای نمایش
unique_id = str(uuid.uuid4())[:8]  # ساخت آیدی یکتا
photo = data["photo"]
file_id = message.video.file_id

waiting[message.from_user.id]["file_id"] = file_id
bot.send_message(message.chat.id, "📝 توضیحات + هشتگ ")

# ================= DELETE COMMAND =================


@bot.message_handler(commands=['delete'])
def delete_movie(message):

    if message.from_user.id not in ADMINS:
        return


data = message.text.split()
if len(data) < 2:
    bot.reply_to(message, "/delete name")
return

delete_movie_db(data[1])
bot.reply_to(message, "🗑 حذف شد")


# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):

    user_id = message.from_user.id


if user_id in ADMINS:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ افزودن فیلم")
    markup.add("📊 آمار")

bot.send_message(message.chat.id, "👑 پنل ادمین", reply_markup=markup)
ensure_connection()
cursor.execute(
    "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
conn.commit()
user_id = message.from_user.id

if not is_joined(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 خصوصی", url=PRIVATE_CHANNEL_LINK))
    markup.add(types.InlineKeyboardButton(
        "📢 عمومی", url=f"https://t.me/{PUBLIC_CHANNEL.replace('@', '')}"))
markup.add(types.InlineKeyboardButton("✅ عضو شدم", callback_data="check"))

bot.send_message(message.chat.id, "❌ اول عضو شو", reply_markup=markup)
return

data = message.text.split()
if len(data) < 2:
    bot.send_message(message.chat.id, "❌ لینک نامعتبر")
return

file_id = get_movie(data[1])

if not file_id:
    bot.send_message(message.chat.id, "❌ پیدا نشد")
return

bot.send_message(message.chat.id, "⚠️ بعد 30 ثانیه حذف میشه")

sent = bot.send_video(message.chat.id, file_id)


def delete():

    time.sleep(DELETE_TIME)


try:
    bot.delete_message(message.chat.id, sent.message_id)
except:
    pass

threading.Thread(target=delete, daemon=True).start()

# ================= CHECK =================


@bot.callback_query_handler(func=lambda call: call.data == "check")
def check(call):

    if is_joined(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ تایید شد")
        bot.send_message(call.message.chat.id, "🎬 حالا لینک بزن")
    else:
        bot.answer_callback_query(call.id, "❌ هنوز نه")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")


def run_web():

    port = int(os.environ.get("PORT", 10000))


server = HTTPServer(("", port), Handler)
server.serve_forever()


@bot.message_handler(func=lambda m: m.text == "➕ افزودن فیلم")
def add_btn(message):

    if message.from_user.id not in ADMINS:
        return


waiting[message.from_user.id] = {}
bot.send_message(message.chat.id, "🎬 اسم فیلم رو بفرست")


@bot.message_handler(func=lambda m: m.from_user.id in waiting and "name" not in waiting[m.from_user.id])
def get_name(message):

    waiting[message.from_user.id]["name"] = message.text


bot.send_message(message.chat.id, "📸 عکس بفرست")


@bot.message_handler(func=lambda m: m.from_user.id in waiting and "file_id" in waiting[m.from_user.id])
def get_desc(message):

    data = waiting[message.from_user.id]


name = data["name"]
photo = data["photo"]
file_id = data["file_id"]
desc = message.text

unique_id = str(uuid.uuid4())[:8]

save_movie(unique_id, file_id)

markup = types.InlineKeyboardMarkup()
markup.add(types.InlineKeyboardButton(
    "⬇️ Download",
    url=f"https://t.me/{BOT_USERNAME}?start={unique_id}"
))

bot.send_photo(
    POST_CHANNEL,
    photo,
    caption=f"🎬 {name}\n\n{desc}",
    has_spoiler=True,
    reply_markup=markup
)

del waiting[message.from_user.id]

bot.send_message(message.chat.id, "✅ فیلم ارسال شد")


@bot.message_handler(func=lambda m: m.text == "📊 آمار")
def stats(message):

    if message.from_user.id not in ADMINS:
        return


cursor.execute("SELECT COUNT(*) FROM users")
count = cursor.fetchone()[0]

bot.send_message(message.chat.id, f"👥 تعداد کاربران: {count}")


# 🚀 اجرای سرور
threading.Thread(target=run_web, daemon=True).start()

print("🚀 Bot Started...")
bot.infinity_polling()
