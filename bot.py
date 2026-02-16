import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# المتغيرات السرية من Railway
TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))
# 👇 معرفك الشخصي (بدون سالب)
OWNER_ID = 6888898698  # معرفك الشخصي

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

# التعامل مع الرسائل المجهولة - بس من الخاص
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # فقط الرسائل الخاصة
    if update.message.chat.type != "private":
        return

    user_id = update.message.from_user.id
    text = update.message.text

    # تسجيل المستخدم إذا جديد
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    # التحقق من الحظر
    cursor.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0] == 1:
        await update.message.reply_text("🚫 تم حظرك من استخدام البوت.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # حفظ الرسالة في قاعدة البيانات
    cursor.execute(
        "INSERT INTO messages (user_id, text, date) VALUES (?, ?, ?)",
        (user_id, text, now)
    )
    conn.commit()

    # ✅ رسالة للمجموعة (مجهولة)
    group_msg = f"📩 رسالة جديدة مجهولة\n\n{text}\n\n🕒 {now}"
    await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=group_msg)
    
    # ✅ رسالة للمالك (مع user_id) - تروح لخاصك
    owner_msg = f"📩 رسالة جديدة\n👤 user_id: {user_id}\n💬 {text}\n🕒 {now}"
    await context.bot.send_message(chat_id=OWNER_ID, text=owner_msg)

    # الرد على المرسل
    await update.message.reply_text("✅ تم إرسال رسالتك بنجاح.")

# أمر حظر المستخدم (للمشرفين والمالك)
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID and update.effective_chat.id != OWNER_ID:
        return
    
    try:
        user_id = int(context.args[0])
        cursor.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await update.message.reply_text(f"🚫 تم حظر المستخدم {user_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم الأمر هكذا: /ban user_id")

# أمر إلغاء حظر المستخدم
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID and update.effective_chat.id != OWNER_ID:
        return
    
    try:
        user_id = int(context.args[0])
        cursor.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم {user_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم الأمر هكذا: /unban user_id")

# أمر إحصائيات
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID and update.effective_chat.id != OWNER_ID:
        return
    
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM messages")
    msgs_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE banned = 1")
    banned_count = cursor.fetchone()[0]
    
    stats_msg = f"📊 إحصائيات البوت:\n\n👥 المستخدمين: {users_count}\n📨 الرسائل: {msgs_count}\n🚫 المحظورين: {banned_count}"
    await update.message.reply_text(stats_msg)

# بناء التطبيق
app = Application.builder().token(TOKEN).build()

# إضافة المعالجات
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# تشغيل البوت
if __name__ == "__main__":
    print("✅ البوت يعمل...")
    print(f"📢 مجموعة المشرفين: {ADMIN_GROUP_ID}")
    print(f"👑 معرف المالك: {OWNER_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
