import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# المتغيرات السرية من Railway
TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))

# تهيئة السجلات
logging.basicConfig(level=logging.INFO)

# تهيئة قاعدة البيانات
conn = sqlite3.connect("messages.db", check_same_thread=False)
cursor = conn.cursor()

# إنشاء الجداول إذا لم تكن موجودة
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    banned INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    date TEXT
)
""")
conn.commit()

# أمر البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أرسل رسالتك بشكل مجهول الآن.")

# التعامل مع الرسائل المجهولة
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # تسجيل المستخدم إذا جديد
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    # التحقق من الحظر
    cursor.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
    banned = cursor.fetchone()[0]

    if banned == 1:
        await update.message.reply_text("🚫 تم حظرك من استخدام البوت.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # حفظ الرسالة بشكل صحيح مع غلق الاقتباس
    cursor.execute(
        "INSERT INTO messages (user_id, text, date) VALUES (?, ?, ?)",
        (user_id, text, now)
    )
    conn.commit()

    # إرسال الرسالة للجروب
    msg = f"📩 رسالة جديدة مجهولة\n\n{text}\n\n🕒 {now}"
    await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=msg)

    # الرد على المرسل
    await update.message.reply_text("✅ تم إرسال رسالتك بنجاح.")

# أمر حظر المستخدم (خاص بالمشرفين)
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    try:
        user_id = int(context.args[0])
        cursor.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await update.message.reply_text("🚫 تم حظر المستخدم.")
    except:
        await update.message.reply_text("❌ استخدم الأمر هكذا: /ban user_id")

# إعداد البوت وتشغيله
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# تشغيل البوت
app.run_polling()
