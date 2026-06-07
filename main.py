from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import psycopg2
import os
import time
import threading
import uuid

# ================= CONFIG =================
TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

ADMINS = [8196100632, 5418159522]

PUBLIC_CHANNEL = "@zapaskaktos1"
PRIVATE_CHANNEL_LINK = "https://t.me/+9b5xs_0PeBBmZTg0"
POST_CHANNEL = -1003939035699

BOT_USERNAME = "Aploderkaktos_bot"
DELETE_TIME = 30

# ================= DB =================


def connect_db():
    while True:
        try:
            conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
            cursor = conn.cursor()
            print("✅ DB Connected")
            return conn, cursor
        except Exception as e:
            print("DB Error:", e)
            time.sleep(5)


conn, cursor = connect_db()


def ensure_connection():
    global conn, cursor
    try:
        cursor.execute("SELECT 1")
    except:
        conn, cursor = connect_db()


cursor.execute("CREATE TABLE IF NOT EXISTS users (id BIGINT PRIMARY KEY)")
cursor.execute(
    "CREATE TABLE IF NOT EXISTS movies (name TEXT PRIMARY KEY, file_id TEXT)")
cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY,
    total_downloads INTEGER DEFAULT 0
)
""")

cursor.execute("""
INSERT INTO stats (id, total_downloads)
VALUES (1,0)
ON CONFLICT (id) DO NOTHING
""")
conn.commit()


@bot.message_handler(func=lambda m: m.text == "📢 ارسال همگانی")
def broadcast_start(message):
    if message.from_user.id not in ADMINS:
        return

    broadcast_waiting.add(message.from_user.id)
    bot.send_message(message.chat.id, "📨 پیام همگانی را ارسال کن")


@bot.message_handler(func=lambda m: m.from_user.id in broadcast_waiting and m.from_user.id in ADMINS)
def broadcast_send(message):

    if message.from_user.id not in ADMINS:
        return

    broadcast_waiting.remove(message.from_user.id)

    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()

    sent_count = 0

    for user in users:

        user_id = user[0]

        if user_id in ADMINS:
            continue

        try:
            bot.send_message(
                user_id,
                f"📢 پیام مدیریت:\n\n{message.text}"
            )

            sent_count += 1

        except:
            pass

    bot.send_message(
        message.chat.id,
        f"✅ پیام برای {sent_count} کاربر ارسال شد"
    )


@bot.callback_query_handler(func=lambda c: c.data == "getmovie")
def get_movie_callback(call):

    user_id = call.from_user.id

    if user_id not in pending_downloads:
        bot.answer_callback_query(call.id, "❌ لینک منقضی شده")
        return

    file_id = pending_downloads[user_id]

    send_video_auto_delete(call.message.chat.id, file_id)

    cursor.execute(
        "UPDATE stats SET total_downloads = total_downloads + 1 WHERE id=1"
    )
    conn.commit()

    del pending_downloads[user_id]

    bot.answer_callback_query(call.id, "🎬 فیلم ارسال شد")


def send_video_auto_delete(chat_id, file_id, delete_after=30):
    sent = bot.send_video(chat_id, file_id)

    # پیام اطلاع
    bot.send_message(
        chat_id, f"⚠️ این ویدیو بعد از {delete_after} ثانیه حذف می‌شود")

    def delete_message_later():
        time.sleep(delete_after)
        try:
            bot.delete_message(chat_id, sent.message_id)
        except Exception as e:
            print("Delete error:", e)

    threading.Thread(
        target=delete_message_later,
        daemon=True
    ).start()

    return sent


# ================= STATE =================
waiting = {}
broadcast_waiting = set()
pending_downloads = {}
# ================= JOIN =================


def is_joined(user_id):
    try:
        member = bot.get_chat_member(PUBLIC_CHANNEL, user_id)
        return member.status not in ["left", "kicked"]
    except:
        return False

# ================= START =================


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    ensure_connection()
    cursor.execute(
        "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    conn.commit()

    if user_id in ADMINS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("➕ افزودن فیلم")
        markup.add("📊 آمار")
        markup.add("📢 ارسال همگانی")

        bot.send_message(message.chat.id, "👑 پنل ادمین", reply_markup=markup)
        return

    if not is_joined(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "📢 خصوصی", url=PRIVATE_CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton(
            "📢 عمومی", url=f"https://t.me/{PUBLIC_CHANNEL.replace('@', '')}"))
        markup.add(types.InlineKeyboardButton(
            "✅ عضو شدم", callback_data="check"))

        bot.send_message(message.chat.id, "❌ اول عضو شو", reply_markup=markup)
        return

    user_id = message.from_user.id

    ensure_connection()
    cursor.execute(
        "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )
    conn.commit()

    if user_id in ADMINS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("➕ افزودن فیلم")
        markup.add("📊 آمار")
        markup.add("📢 ارسال همگانی")

        bot.send_message(message.chat.id, "👑 پنل ادمین", reply_markup=markup)
        return

    if not is_joined(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "📢 خصوصی", url=PRIVATE_CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton(
            "📢 عمومی", url=f"https://t.me/{PUBLIC_CHANNEL.replace('@', '')}"))
        markup.add(types.InlineKeyboardButton(
            "✅ عضو شدم", callback_data="check"))

        bot.send_message(message.chat.id, "❌ اول عضو شو", reply_markup=markup)
        return

    args = message.text.split()

    if len(args) > 1:
    movie_id = args[1]

    file_id = get_movie(movie_id)

    if not file_id:
        bot.send_message(message.chat.id, "❌ فیلم پیدا نشد")
        return

    pending_downloads[user_id] = file_id

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✅ ری‌اکشن زدم | دریافت فیلم",
            callback_data="getmovie"
        )
    )

    bot.send_message(
        message.chat.id,
        "⭐ لطفاً روی پست موردنظر ری‌اکشن بزنید.\n\nبعد روی دکمه زیر بزنید تا فیلم ارسال شود.",
        reply_markup=markup
    )
    return

# ================= CHECK =================


@bot.callback_query_handler(func=lambda c: c.data == "check")
def check(call):
    if is_joined(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ تایید شد")
    else:
        bot.answer_callback_query(call.id, "❌ هنوز نه")

# ================= ADD FLOW =================


@bot.message_handler(func=lambda m: m.text == "➕ افزودن فیلم")
def add_btn(message):
    if message.from_user.id not in ADMINS:
        return

    waiting[message.from_user.id] = {"step": "photo"}
    bot.send_message(message.chat.id, "📸 عکس بفرست")


@bot.message_handler(content_types=['photo'])
def get_photo(message):
    if message.from_user.id not in waiting:
        return

    if waiting[message.from_user.id].get("step") != "photo":
        return

    waiting[message.from_user.id]["photo"] = message.photo[-1].file_id
    waiting[message.from_user.id]["step"] = "video"

    bot.send_message(message.chat.id, "🎬 ویدیو بفرست")


@bot.message_handler(content_types=['video'])
def get_video(message):
    if message.from_user.id not in waiting:
        return

    if waiting[message.from_user.id].get("step") != "video":
        return

    waiting[message.from_user.id]["file_id"] = message.video.file_id
    waiting[message.from_user.id]["step"] = "desc"

    bot.send_message(message.chat.id, "📝 توضیحات بفرست")


@bot.message_handler(func=lambda m: m.from_user.id in waiting and waiting[m.from_user.id].get("step") == "desc")
def get_desc(message):
    data = waiting[message.from_user.id]

    unique_id = str(uuid.uuid4())[:8]

    cursor.execute(
        "INSERT INTO movies (name, file_id) VALUES (%s,%s) ON CONFLICT (name) DO UPDATE SET file_id = EXCLUDED.file_id",
        (unique_id, data["file_id"])
    )
    conn.commit()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "⬇️ دانلود",
        url=f"https://t.me/{BOT_USERNAME}?start={unique_id}"
    ))

    bot.send_photo(
        POST_CHANNEL,
        data["photo"],
        caption=message.text,
        reply_markup=markup,
        has_spoiler=True
    )

    del waiting[message.from_user.id]
    bot.send_message(message.chat.id, "✅ ارسال شد")

# ================= STATS =================


@bot.message_handler(func=lambda m: m.text == "📊 آمار")
def stats(message):
    if message.from_user.id not in ADMINS:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]

    cursor.execute("SELECT total_downloads FROM stats WHERE id=1")
    downloads = cursor.fetchone()[0]

    bot.send_message(
        message.chat.id,
        f"👥 کاربران: {users_count}\n\n⬇️ کل دانلودها: {downloads}"
    )

# ================= DB =================


def get_movie(name):
    cursor.execute("SELECT file_id FROM movies WHERE name=%s", (name,))
    r = cursor.fetchone()
    return r[0] if r else None

# ================= WEB SERVER =================


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("", port), Handler)
    server.serve_forever()


threading.Thread(target=run_web).start()

# ================= RUN =================
print("🚀 Started")
bot.remove_webhook()
bot.infinity_polling(
    skip_pending=True,
    timeout=30,
    long_polling_timeout=30
)
