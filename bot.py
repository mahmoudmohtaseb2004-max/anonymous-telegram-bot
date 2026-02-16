import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# المتغيرات السرية من Railway
TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))
OWNER_ID = 6888898698  # معرفك

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
        photo = update.message.photo[-1]
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

    # إرسال للمجموعة (حسب نوع الوسائط)
    if file_type == "text":
        group_msg = f"📩 رسالة جديدة مجهولة\n\n{media_text}\n\n🕒 {now}"
        sent_message = await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=group_msg)
        
    elif file_type == "photo":
        group_caption = f"📸 صورة جديدة\n\n{caption}\n\n🕒 {now}"
        sent_message = await context.bot.send_photo(
            chat_id=ADMIN_GROUP_ID, 
            photo=file_id,
            caption=group_caption
        )
        
    elif file_type == "voice":
        group_caption = f"🎤 رسالة صوتية\n\n🕒 {now}"
        sent_message = await context.bot.send_voice(
            chat_id=ADMIN_GROUP_ID,
            voice=file_id,
            caption=group_caption
        )
        
    elif file_type == "video":
        group_caption = f"🎥 فيديو جديد\n\n{caption}\n\n🕒 {now}"
        sent_message = await context.bot.send_video(
            chat_id=ADMIN_GROUP_ID,
            video=file_id,
            caption=group_caption
        )
        
    elif file_type == "audio":
        group_caption = f"🎵 ملف صوتي\n\n{caption}\n\n🕒 {now}"
        sent_message = await context.bot.send_audio(
            chat_id=ADMIN_GROUP_ID,
            audio=file_id,
            caption=group_caption
        )
        
    elif file_type == "document":
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
    
    # إرسال للمالك (خاص بدون user_id)
    sender_name = f"@{username}" if username else first_name
    owner_msg = f"📩 رسالة جديدة من {sender_name}\n{media_text}\n🕒 {now}"
    await context.bot.send_message(chat_id=OWNER_ID, text=owner_msg)

    # إذا كانت وسائط، أرسل نسخة للمالك
    if file_type != "text":
        if file_type == "photo":
            await context.bot.send_photo(
                chat_id=OWNER_ID,
                photo=file_id,
                caption=f"📸 من {sender_name}\n{caption}"
            )
        elif file_type == "voice":
            await context.bot.send_voice(
                chat_id=OWNER_ID,
                voice=file_id,
                caption=f"🎤 من {sender_name}"
            )
        elif file_type == "video":
            await context.bot.send_video(
                chat_id=OWNER_ID,
                video=file_id,
                caption=f"🎥 من {sender_name}\n{caption}"
            )
        elif file_type == "audio":
            await context.bot.send_audio(
                chat_id=OWNER_ID,
                audio=file_id,
                caption=f"🎵 من {sender_name}\n{caption}"
            )
        elif file_type == "document":
            await context.bot.send_document(
                chat_id=OWNER_ID,
                document=file_id,
                caption=f"📎 من {sender_name}\n{caption}"
            )

    # الرد على المرسل
    await update.message.reply_text("✅ تم إرسال رسالتك بنجاح.")

# التعامل مع الردود من المجموعة (بجميع أنواعها)
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
    
    if not result:
        await update.message.reply_text("❌ لم أجد المستخدم لهذه الرسالة")
        return
        
    user_id = result[0]
    
    # تحديد نوع رد المشرف
    try:
        if update.message.text:
            # رد نصي
            reply_msg = f"📨 رد من الإدارة:\n\n{update.message.text}"
            await context.bot.send_message(chat_id=user_id, text=reply_msg)
            
        elif update.message.photo:
            # رد بصورة
            photo = update.message.photo[-1]
            caption = "📸 رد من الإدارة بصورة"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_photo(chat_id=user_id, photo=photo.file_id, caption=caption)
            
        elif update.message.voice:
            # رد بفويس
            voice = update.message.voice
            caption = "🎤 رد من الإدارة بصوت"
            await context.bot.send_voice(chat_id=user_id, voice=voice.file_id, caption=caption)
            
        elif update.message.video:
            # رد بفيديو
            video = update.message.video
            caption = "🎥 رد من الإدارة بفيديو"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_video(chat_id=user_id, video=video.file_id, caption=caption)
            
        elif update.message.document:
            # رد بملف
            document = update.message.document
            caption = f"📎 رد من الإدارة بملف: {document.file_name}"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_document(chat_id=user_id, document=document.file_id, caption=caption)
            
        elif update.message.audio:
            # رد بملف صوتي
            audio = update.message.audio
            caption = "🎵 رد من الإدارة بملف صوتي"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_audio(chat_id=user_id, audio=audio.file_id, caption=caption)
            
        elif update.message.sticker:
            # رد بملصق
            sticker = update.message.sticker
            await context.bot.send_sticker(chat_id=user_id, sticker=sticker.file_id)
            await update.message.reply_text("✅ تم إرسال الملصق للمستخدم")
            return
            
        else:
            await update.message.reply_text("❌ نوع الرد غير مدعوم")
            return
        
        # تأكيد للمشرف
        await update.message.reply_text("✅ تم إرسال ردك للمستخدم")
        
        # إشعار للمالك (اختياري)
        sender_name = update.message.from_user.username or update.message.from_user.first_name
        await context.bot.send_message(
            chat_id=OWNER_ID, 
            text=f"✅ {sender_name} رد على المستخدم {user_id}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

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
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

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
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Chat(ADMIN_GROUP_ID) & filters.REPLY, handle_group_reply))
app.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_private_message))

# تشغيل البوت
if __name__ == "__main__":
    print("✅ البوت يعمل مع دعم الوسائط والردود المتعددة...")
    print(f"📢 مجموعة المشرفين: {ADMIN_GROUP_ID}")
    print(f"👑 معرف المالك: {OWNER_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
