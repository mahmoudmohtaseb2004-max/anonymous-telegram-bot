import logging
import sqlite3
import os
from datetime import datetime
import pytz
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

# الحصول على الوقت حسب العراق
def get_iraq_time():
    tz = pytz.timezone('Asia/Baghdad')
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

# أمر البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أرسل رسالتك بشكل مجهول الآن.\n\n"
        "📝 تقدر ترسل:\n"
        "• نصوص\n"
        "• صور 📸\n"
        "• فويسات 🎤\n"
        "• فيديوهات 🎥\n"
        "• ملفات 📎\n"
        "• ملصقات 🎭"
    )

# التعامل مع الرسائل من الخاص
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return

    user_id = update.message.from_user.id
    user = update.message.from_user
    username = user.username
    first_name = user.first_name

    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    cursor.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0] == 1:
        await update.message.reply_text("🚫 تم حظرك من استخدام البوت.")
        return

    now = get_iraq_time()
    
    file_id = None
    file_type = None
    caption = None
    media_text = ""
    
    if update.message.text:
        media_text = update.message.text
        file_type = "text"
        caption = None
        
    elif update.message.photo:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        file_type = "photo"
        caption = update.message.caption or ""
        media_text = f"[صورة] {caption}"
        
    elif update.message.voice:
        voice = update.message.voice
        file_id = voice.file_id
        file_type = "voice"
        caption = None
        media_text = "[تسجيل صوتي]"
        
    elif update.message.video:
        video = update.message.video
        file_id = video.file_id
        file_type = "video"
        caption = update.message.caption or ""
        media_text = f"[فيديو] {caption}"
        
    elif update.message.audio:
        audio = update.message.audio
        file_id = audio.file_id
        file_type = "audio"
        caption = update.message.caption or ""
        media_text = f"[ملف صوتي] {caption}"
        
    elif update.message.document:
        document = update.message.document
        file_id = document.file_id
        file_type = "document"
        caption = update.message.caption or ""
        media_text = f"[ملف: {document.file_name}] {caption}"
        
    elif update.message.sticker:
        sticker = update.message.sticker
        file_id = sticker.file_id
        file_type = "sticker"
        caption = None
        media_text = "[ملصق]"
        
    else:
        await update.message.reply_text("❌ نوع الرسالة غير مدعوم.")
        return

    cursor.execute(
        """INSERT INTO messages 
           (user_id, text, caption, file_id, file_type, date) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, media_text, caption, file_id, file_type, now)
    )
    conn.commit()
    
    message_db_id = cursor.lastrowid

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
        
    elif file_type == "sticker":
        sent_message = await context.bot.send_sticker(
            chat_id=ADMIN_GROUP_ID,
            sticker=file_id
        )
    
    cursor.execute(
        "UPDATE messages SET group_message_id = ? WHERE id = ?",
        (sent_message.message_id, message_db_id)
    )
    conn.commit()
    
    # إرسال للمالك (فقط يوزر + الرسالة بدون كلام زيادة)
    sender_name = f"@{username}" if username else first_name
    owner_msg = f"{sender_name}\n{media_text}"
    await context.bot.send_message(chat_id=OWNER_ID, text=owner_msg)

    if file_type != "text":
        if file_type == "photo":
            await context.bot.send_photo(
                chat_id=OWNER_ID,
                photo=file_id,
                caption=f"{sender_name}"
            )
        elif file_type == "voice":
            await context.bot.send_voice(
                chat_id=OWNER_ID,
                voice=file_id,
                caption=f"{sender_name}"
            )
        elif file_type == "video":
            await context.bot.send_video(
                chat_id=OWNER_ID,
                video=file_id,
                caption=f"{sender_name}"
            )
        elif file_type == "audio":
            await context.bot.send_audio(
                chat_id=OWNER_ID,
                audio=file_id,
                caption=f"{sender_name}"
            )
        elif file_type == "document":
            await context.bot.send_document(
                chat_id=OWNER_ID,
                document=file_id,
                caption=f"{sender_name}"
            )
        elif file_type == "sticker":
            await context.bot.send_sticker(
                chat_id=OWNER_ID,
                sticker=file_id
            )

# التعامل مع الردود من المجموعة
async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # منع البوت من معالجة رسائله هو
    if update.message.from_user.id == context.bot.id:
        return
    
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if not update.message.reply_to_message:
        return
    
    replied_message_id = update.message.reply_to_message.message_id
    
    cursor.execute("SELECT user_id FROM messages WHERE group_message_id = ?", (replied_message_id,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("❌ لم أجد المستخدم لهذه الرسالة")
        return
        
    user_id = result[0]
    
    # معلومات المشرف
    admin = update.message.from_user
    admin_username = admin.username
    admin_name = admin.first_name
    admin_display = f"@{admin_username}" if admin_username else admin_name
    
    try:
        if update.message.text:
            # رد نصي
            reply_msg = f"📨 رد من الإدارة:\n\n{update.message.text}"
            await context.bot.send_message(chat_id=user_id, text=reply_msg)
            
            # إرسال الرد للاونر
            owner_reply_msg = f"{admin_display}\n{update.message.text}"
            await context.bot.send_message(chat_id=OWNER_ID, text=owner_reply_msg)
            
        elif update.message.photo:
            # رد بصورة
            photo = update.message.photo[-1]
            caption = "📸 رد من الإدارة بصورة"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_photo(chat_id=user_id, photo=photo.file_id, caption=caption)
            
            # إرسال الرد للاونر
            await context.bot.send_photo(
                chat_id=OWNER_ID,
                photo=photo.file_id,
                caption=f"{admin_display}"
            )
            
        elif update.message.voice:
            # رد بفويس
            voice = update.message.voice
            caption = "🎤 رد من الإدارة بصوت"
            await context.bot.send_voice(chat_id=user_id, voice=voice.file_id, caption=caption)
            
            # إرسال الرد للاونر
            await context.bot.send_voice(
                chat_id=OWNER_ID,
                voice=voice.file_id,
                caption=f"{admin_display}"
            )
            
        elif update.message.video:
            # رد بفيديو
            video = update.message.video
            caption = "🎥 رد من الإدارة بفيديو"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_video(chat_id=user_id, video=video.file_id, caption=caption)
            
            # إرسال الرد للاونر
            await context.bot.send_video(
                chat_id=OWNER_ID,
                video=video.file_id,
                caption=f"{admin_display}"
            )
            
        elif update.message.document:
            # رد بملف
            document = update.message.document
            caption = f"📎 رد من الإدارة بملف: {document.file_name}"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_document(chat_id=user_id, document=document.file_id, caption=caption)
            
            # إرسال الرد للاونر
            await context.bot.send_document(
                chat_id=OWNER_ID,
                document=document.file_id,
                caption=f"{admin_display}"
            )
            
        elif update.message.audio:
            # رد بملف صوتي
            audio = update.message.audio
            caption = "🎵 رد من الإدارة بملف صوتي"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_audio(chat_id=user_id, audio=audio.file_id, caption=caption)
            
            # إرسال الرد للاونر
            await context.bot.send_audio(
                chat_id=OWNER_ID,
                audio=audio.file_id,
                caption=f"{admin_display}"
            )
            
        elif update.message.sticker:
            # رد بملصق
            sticker = update.message.sticker
            await context.bot.send_sticker(chat_id=user_id, sticker=sticker.file_id)
            
            # إرسال الرد للاونر
            await context.bot.send_sticker(chat_id=OWNER_ID, sticker=sticker.file_id)
            return
            
        else:
            await update.message.reply_text("❌ نوع الرد غير مدعوم")
            return
        
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

# أمر البث للمستخدمين
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من أن الأمر من المجموعة المسموحة أو من المالك
    if update.effective_chat.id != ADMIN_GROUP_ID and update.effective_chat.id != OWNER_ID:
        return
    
    # التحقق من وجود نص للبث
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("❌ استخدم الأمر هكذا:\n/bd نص الرسالة\nأو قم بالرد على رسالة بالبث")
        return
    
    # الحصول على نص البث
    broadcast_text = ""
    if context.args:
        broadcast_text = " ".join(context.args)
    elif update.message.reply_to_message:
        if update.message.reply_to_message.text:
            broadcast_text = update.message.reply_to_message.text
        elif update.message.reply_to_message.caption:
            broadcast_text = update.message.reply_to_message.caption
        else:
            await update.message.reply_text("❌ لا يمكن بث هذا النوع من الرسائل")
            return
    
    # إرسال رسالة بدء البث
    status_msg = await update.message.reply_text("🔄 جاري بدء البث...")
    
    # جلب جميع المستخدمين من قاعدة البيانات
    cursor.execute("SELECT user_id FROM users WHERE banned = 0")
    users = cursor.fetchall()
    
    if not users:
        await status_msg.edit_text("❌ لا يوجد مستخدمين للبث")
        return
    
    success_count = 0
    fail_count = 0
    
    # إرسال البث لكل مستخدم
    for user in users:
        user_id = user[0]
        try:
            # إذا كان هناك وسائط في الرسالة المردود عليها
            if update.message.reply_to_message:
                replied = update.message.reply_to_message
                
                # بث الصور
                if replied.photo:
                    photo = replied.photo[-1]
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=photo.file_id,
                        caption=broadcast_text if broadcast_text else None
                    )
                
                # بث الفيديو
                elif replied.video:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=replied.video.file_id,
                        caption=broadcast_text
                    )
                
                # بث الصوت
                elif replied.voice:
                    await context.bot.send_voice(
                        chat_id=user_id,
                        voice=replied.voice.file_id,
                        caption=broadcast_text
                    )
                
                # بث الملفات
                elif replied.document:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=replied.document.file_id,
                        caption=broadcast_text
                    )
                
                # بث الملصقات
                elif replied.sticker:
                    await context.bot.send_sticker(
                        chat_id=user_id,
                        sticker=replied.sticker.file_id
                    )
                
                # بث النصوص
                else:
                    await context.bot.send_message(chat_id=user_id, text=broadcast_text)
            
            # إذا كان البث نص عادي
            else:
                await context.bot.send_message(chat_id=user_id, text=broadcast_text)
            
            success_count += 1
            
        except Exception as e:
            fail_count += 1
            logging.error(f"فشل إرسال البث للمستخدم {user_id}: {str(e)}")
    
    # إرسال تقرير البث
    report = f"✅ تم البث بنجاح!\n\n📊 الإحصائيات:\n✓ تم الإرسال لـ: {success_count} مستخدم\n✗ فشل الإرسال لـ: {fail_count} مستخدم"
    
    await status_msg.edit_text(report)
    
    # إرسال التقرير للمالك أيضاً
    if update.effective_chat.id != OWNER_ID:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"📢 تم تنفيذ أمر بث بواسطة {update.effective_user.first_name}\n\n{report}"
        )

# بناء التطبيق
app = Application.builder().token(TOKEN).build()

# إضافة المعالجات
app.add_handler(CommandHandler("bd", broadcast))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(filters.ALL & filters.Chat(ADMIN_GROUP_ID) & filters.REPLY, handle_group_reply))
app.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_private_message))

# تشغيل البوت
if __name__ == "__main__":
    print("✅ البوت يعمل مع دعم الستيكرات وأمر البث...")
    print(f"📢 مجموعة المشرفين: {ADMIN_GROUP_ID}")
    print(f"👑 معرف المالك: {OWNER_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
