import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# المتغيرات السرية من Railway
TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))
OWNER_ID = 6888898698

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
    caption TEXT,
    file_id TEXT,
    file_type TEXT,
    date TEXT,
    group_message_id INTEGER
)
""")
conn.commit()

# أمر البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أرسل رسالتك بشكل مجهول الآن.\n\n"
        "📝 تقدر ترسل:\n"
        "• نصوص\n"
        "• صور 📸\n"
        "• فويسات 🎤\n"
        "• فيديوهات 🎥\n"
        "• ملفات 📎"
    )

# التعامل مع الرسائل من الخاص
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return

    user_id = update.message.from_user.id
    user = update.message.from_user
    username = user.username
    first_name = user.first_name

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
    
    # متغيرات للرسالة
    file_id = None
    file_type = None
    caption = None
    media_text = ""
    
    # تحديد نوع الرسالة
    if update.message.text:
        # رسالة نصية
        media_text = update.message.text
        file_type = "text"
        caption = None
        
    elif update.message.photo:
        # صورة
        photo = update.message.photo[-1]  # أعلى دقة
        file_id = photo.file_id
        file_type = "photo"
        caption = update.message.caption or ""
        media_text = f"[صورة] {caption}"
        
    elif update.message.voice:
        # فويس
        voice = update.message.voice
        file_id = voice.file_id
        file_type = "voice"
        caption = None
        media_text = "[تسجيل صوتي]"
        
    elif update.message.video:
        # فيديو
        video = update.message.video
        file_id = video.file_id
        file_type = "video"
        caption = update.message.caption or ""
        media_text = f"[فيديو] {caption}"
        
    elif update.message.audio:
        # ملف صوتي
        audio = update.message.audio
        file_id = audio.file_id
        file_type = "audio"
        caption = update.message.caption or ""
        media_text = f"[ملف صوتي] {caption}"
        
    elif update.message.document:
        # ملف
        document = update.message.document
        file_id = document.file_id
        file_type = "document"
        caption = update.message.caption or ""
        media_text = f"[ملف: {document.file_name}] {caption}"
        
    else:
        # نوع غير مدعوم
        await update.message.reply_text("❌ نوع الرسالة غير مدعوم.")
        return

    # حفظ الرسالة في قاعدة البيانات
    cursor.execute(
        """INSERT INTO messages 
           (user_id, text, caption, file_id, file_type, date) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, media_text, caption, file_id, file_type, now)
    )
    conn.commit()
    
    message_db_id = cursor.lastrowid

    # ✅ إرسال للمجموعة (حسب نوع الوسائط)
    if file_type == "text":
        # رسالة نصية
        group_msg = f"📩 رسالة جديدة مجهولة\n\n{media_text}\n\n🕒 {now}"
        sent_message = await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=group_msg)
        
    elif file_type == "photo":
        # صورة
        group_caption = f"📸 صورة جديدة\n\n{caption}\n\n🕒 {now}"
        sent_message = await context.bot.send_photo(
            chat_id=ADMIN_GROUP_ID, 
            photo=file_id,
            caption=group_caption
        )
        
    elif file_type == "voice":
        # فويس
        group_caption = f"🎤 رسالة صوتية\n\n🕒 {now}"
        sent_message = await context.bot.send_voice(
            chat_id=ADMIN_GROUP_ID,
            voice=file_id,
            caption=group_caption
        )
        
    elif file_type == "video":
        # فيديو
        group_caption = f"🎥 فيديو جديد\n\n{caption}\n\n🕒 {now}"
        sent_message = await context.bot.send_video(
            chat_id=ADMIN_GROUP_ID,
            video=file_id,
            caption=group_caption
        )
        
    elif file_type == "audio":
        # ملف صوتي
        group_caption = f"🎵 ملف صوتي\n\n{caption}\n\n🕒 {now}"
        sent_message = await context.bot.send_audio(
            chat_id=ADMIN_GROUP_ID,
            audio=file_id,
            caption=group_caption
        )
        
    elif file_type == "document":
        # ملف
        group_caption = f"📎 ملف: {update.message.document.file_name}\n\n{caption}\n\n🕒 {now}"
        sent_message = await context.bot.send_document(
            chat_id=ADMIN_GROUP_ID,
            document=file_id,
            caption=group_caption
        )
    
    # تحديث group_message_id في قاعدة البيانات
    cursor.execute(
        "UPDATE messages SET group_message_id = ? WHERE id = ?",
        (sent_message.message_id, message_db_id)
    )
    conn.commit()
    
    # ✅ إرسال للمالك (خاص)
    if username:
        owner_msg = f"📩 رسالة جديدة من @{username}\n{media_text}\n🕒 {now}"
    else:
        owner_msg = f"📩 رسالة جديدة من {first_name} (ID: {user_id})\n{media_text}\n🕒 {now}"
    
    await context.bot.send_message(chat_id=OWNER_ID, text=owner_msg)

    # الرد على المرسل
    await update.message.reply_text("✅ تم إرسال رسالتك بنجاح.")

# التعامل مع الردود من المجموعة
async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if not update.message.reply_to_message:
        return
    
    # جلب ID الرسالة الأصلية في المجموعة
    replied_message_id = update.message.reply_to_message.message_id
    
    # البحث عن المستخدم صاحب الرسالة
    cursor.execute("SELECT user_id FROM messages WHERE group_message_id = ?", (replied_message_id,))
    result = cursor.fetchone()
    
    if result:
        user_id = result[0]
        reply_text = update.message.text
        
        # إرسال الرد للمستخدم
        reply_msg = f"📨 رد من الإدارة:\n\n{reply_text}"
        await context.bot.send_message(chat_id=user_id, text=reply_msg)
        
        # تأكيد للمشرف
        await update.message.reply_text("✅ تم إرسال ردك للمستخدم")
    else:
        await update.message.reply_text("❌ لم أجد المستخدم لهذه الرسالة")

# أمر حظر المستخدم
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
    
    cursor.execute("SELECT file_type, COUNT(*) FROM messages GROUP BY file_type")
    media_stats = cursor.fetchall()
    
    stats_msg = f"📊 إحصائيات البوت:\n\n👥 المستخدمين: {users_count}\n📨 الرسائل: {msgs_count}\n🚫 المحظورين: {banned_count}\n\n📸 صور: {sum(1 for t,c in media_stats if t=='photo')}\n🎤 فويسات: {sum(1 for t,c in media_stats if t=='voice')}\n🎥 فيديوهات: {sum(1 for t,c in media_stats if t=='video')}\n📎 ملفات: {sum(1 for t,c in media_stats if t=='document')}"
    await update.message.reply_text(stats_msg)

# بناء التطبيق
app = Application.builder().token(TOKEN).build()

# إضافة المعالجات
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Chat(ADMIN_GROUP_ID), handle_group_reply))
app.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_private_message))

# تشغيل البوت
if __name__ == "__main__":
    print("✅ البوت يعمل مع دعم الوسائط...")
    print(f"📢 مجموعة المشرفين: {ADMIN_GROUP_ID}")
    print(f"👑 معرف المالك: {OWNER_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
