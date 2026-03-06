import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    CommandHandler
)

# =====================
# الإعدادات
# =====================

BOT_TOKEN = "PUT_BOT_TOKEN_HERE"
ADMIN_GROUP_ID = -1001234567890


# =====================
# قاعدة البيانات
# =====================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
user_id INTEGER PRIMARY KEY,
username TEXT,
first_name TEXT,
banned INTEGER DEFAULT 0,
messages_count INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
group_message_id INTEGER,
date TEXT
)
""")

conn.commit()


# =====================
# الوقت
# =====================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =====================
# حفظ المستخدم
# =====================

def save_user(user):

    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, username, first_name)
    VALUES (?,?,?)
    """,(user.id,user.username,user.first_name))

    cursor.execute("""
    UPDATE users
    SET messages_count = messages_count + 1
    WHERE user_id=?
    """,(user.id,))

    conn.commit()


# =====================
# فحص الحظر
# =====================

def is_banned(user_id):

    cursor.execute(
        "SELECT banned FROM users WHERE user_id=?",
        (user_id,)
    )

    r = cursor.fetchone()

    if r and r[0] == 1:
        return True

    return False


# =====================
# استقبال رسائل الخاص
# =====================

async def private_message(update:Update,context:ContextTypes.DEFAULT_TYPE):

    msg = update.message
    user = msg.from_user

    if is_banned(user.id):

        await msg.reply_text("🚫 تم حظرك من استخدام البوت")
        return

    save_user(user)

    sender = f"@{user.username}" if user.username else user.first_name

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 معلومات",callback_data=f"info_{user.id}"),
            InlineKeyboardButton("🚫 حظر",callback_data=f"ban_{user.id}")
        ]
    ])

    await context.bot.send_message(
        ADMIN_GROUP_ID,
        f"👤 {sender}\n🆔 {user.id}",
        reply_markup=keyboard
    )

    sent=None

    if msg.text:

        sent=await context.bot.send_message(
            ADMIN_GROUP_ID,
            msg.text
        )

    elif msg.photo:

        sent=await context.bot.send_photo(
            ADMIN_GROUP_ID,
            msg.photo[-1].file_id,
            caption=msg.caption
        )

    elif msg.voice:

        sent=await context.bot.send_voice(
            ADMIN_GROUP_ID,
            msg.voice.file_id
        )

    elif msg.video:

        sent=await context.bot.send_video(
            ADMIN_GROUP_ID,
            msg.video.file_id,
            caption=msg.caption
        )

    elif msg.document:

        sent=await context.bot.send_document(
            ADMIN_GROUP_ID,
            msg.document.file_id,
            caption=msg.caption
        )

    elif msg.sticker:

        sent=await context.bot.send_sticker(
            ADMIN_GROUP_ID,
            msg.sticker.file_id
        )

    if sent:

        cursor.execute("""
        INSERT INTO messages(user_id,group_message_id,date)
        VALUES (?,?,?)
        """,(user.id,sent.message_id,now()))

        conn.commit()


# =====================
# الرد من الأدمن
# =====================

async def admin_reply(update:Update,context:ContextTypes.DEFAULT_TYPE):

    msg = update.message

    if msg.chat.id != ADMIN_GROUP_ID:
        return

    if not msg.reply_to_message:
        return

    gid = msg.reply_to_message.message_id

    cursor.execute(
        "SELECT user_id FROM messages WHERE group_message_id=?",
        (gid,)
    )

    r=cursor.fetchone()

    if not r:
        return

    user_id=r[0]

    if msg.text:

        await context.bot.send_message(
            user_id,
            f"💬 رد الإدارة\n\n{msg.text}"
        )

    elif msg.photo:

        await context.bot.send_photo(
            user_id,
            msg.photo[-1].file_id,
            caption=msg.caption
        )


# =====================
# أزرار الإدارة
# =====================

async def buttons(update:Update,context:ContextTypes.DEFAULT_TYPE):

    q=update.callback_query
    await q.answer()

    data=q.data.split("_")

    action=data[0]
    user_id=int(data[1])

    if action=="ban":

        cursor.execute(
            "UPDATE users SET banned=1 WHERE user_id=?",
            (user_id,)
        )
        conn.commit()

        await q.edit_message_text("🚫 تم حظر المستخدم")

    elif action=="info":

        cursor.execute(
        "SELECT username,first_name,messages_count FROM users WHERE user_id=?",
        (user_id,)
        )

        u=cursor.fetchone()

        await q.message.reply_text(
f"""
👤 معلومات المستخدم

ID : {user_id}
Username : @{u[0]}
Name : {u[1]}
Messages : {u[2]}
"""
        )


# =====================
# أوامر الإدارة
# =====================

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):

    cursor.execute("SELECT COUNT(*) FROM users")
    users=cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages")
    msgs=cursor.fetchone()[0]

    await update.message.reply_text(
f"""
📊 احصائيات البوت

👥 المستخدمين : {users}
💬 الرسائل : {msgs}
"""
    )


# =====================
# تشغيل البوت
# =====================

def main():

    app=Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.ChatType.PRIVATE,private_message))

    app.add_handler(MessageHandler(filters.Chat(ADMIN_GROUP_ID),admin_reply))

    app.add_handler(CallbackQueryHandler(buttons))

    app.add_handler(CommandHandler("stats",stats))

    print("Bot Running...")

    app.run_polling()


if __name__=="__main__":
    main()
