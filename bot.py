import os
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
# الإعدادات - متغيرات البيئة
# =====================

BOT_TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))

# التأكد من وجود المتغيرات
if not BOT_TOKEN:
    raise ValueError("❌ لم يتم العثور على TOKEN في متغيرات البيئة!")

if not ADMIN_GROUP_ID:
    raise ValueError("❌ لم يتم العثور على ADMIN_GROUP_ID في متغيرات البيئة!")


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
    """, (user.id, user.username, user.first_name))

    cursor.execute("""
    UPDATE users
    SET messages_count = messages_count + 1
    WHERE user_id=?
    """, (user.id,))

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

async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user

    if is_banned(user.id):
        await msg.reply_text("🚫 تم حظرك من استخدام البوت")
        return

    save_user(user)

    sender = f"@{user.username}" if user.username else user.first_name

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 معلومات", callback_data=f"info_{user.id}"),
            InlineKeyboardButton("🚫 حظر", callback_data=f"ban_{user.id}")
        ]
    ])

    # إرسال رسالة منفصلة تحتوي على معلومات المرسل
    await context.bot.send_message(
        ADMIN_GROUP_ID,
        f"👤 {sender}\n🆔 {user.id}",
        reply_markup=keyboard
    )

    sent = None

    # إرسال محتوى الرسالة في رسالة منفصلة
    if msg.text:
        sent = await context.bot.send_message(
            ADMIN_GROUP_ID,
            msg.text
        )

    elif msg.photo:
        sent = await context.bot.send_photo(
            ADMIN_GROUP_ID,
            msg.photo[-1].file_id,
            caption=msg.caption
        )

    elif msg.voice:
        sent = await context.bot.send_voice(
            ADMIN_GROUP_ID,
            msg.voice.file_id
        )

    elif msg.video:
        sent = await context.bot.send_video(
            ADMIN_GROUP_ID,
            msg.video.file_id,
            caption=msg.caption
        )

    elif msg.document:
        sent = await context.bot.send_document(
            ADMIN_GROUP_ID,
            msg.document.file_id,
            caption=msg.caption
        )

    elif msg.sticker:
        sent = await context.bot.send_sticker(
            ADMIN_GROUP_ID,
            msg.sticker.file_id
        )

    elif msg.audio:
        sent = await context.bot.send_audio(
            ADMIN_GROUP_ID,
            msg.audio.file_id,
            caption=msg.caption
        )

    elif msg.video_note:
        sent = await context.bot.send_video_note(
            ADMIN_GROUP_ID,
            msg.video_note.file_id
        )

    elif msg.animation:
        sent = await context.bot.send_animation(
            ADMIN_GROUP_ID,
            msg.animation.file_id,
            caption=msg.caption
        )

    if sent:
        cursor.execute("""
        INSERT INTO messages(user_id, group_message_id, date)
        VALUES (?,?,?)
        """, (user.id, sent.message_id, now()))
        conn.commit()


# =====================
# الرد من الأدمن
# =====================

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    r = cursor.fetchone()

    if not r:
        await msg.reply_text("❌ لم أجد المستخدم لهذه الرسالة")
        return

    user_id = r[0]

    try:
        if msg.text:
            await context.bot.send_message(
                user_id,
                f"💬 رد من الإدارة\n\n{msg.text}"
            )

        elif msg.photo:
            await context.bot.send_photo(
                user_id,
                msg.photo[-1].file_id,
                caption=f"📸 رد من الإدارة بصورة\n\n{msg.caption}" if msg.caption else "📸 رد من الإدارة بصورة"
            )

        elif msg.voice:
            await context.bot.send_voice(
                user_id,
                msg.voice.file_id,
                caption="🎤 رد من الإدارة بصوت"
            )

        elif msg.video:
            await context.bot.send_video(
                user_id,
                msg.video.file_id,
                caption=f"🎥 رد من الإدارة بفيديو\n\n{msg.caption}" if msg.caption else "🎥 رد من الإدارة بفيديو"
            )

        elif msg.document:
            await context.bot.send_document(
                user_id,
                msg.document.file_id,
                caption=f"📎 رد من الإدارة بملف\n\n{msg.caption}" if msg.caption else "📎 رد من الإدارة بملف"
            )

        elif msg.sticker:
            await context.bot.send_sticker(
                user_id,
                msg.sticker.file_id
            )
            # لا نرسل رسالة نصية مع الستيكر

        elif msg.audio:
            await context.bot.send_audio(
                user_id,
                msg.audio.file_id,
                caption=f"🎵 رد من الإدارة بصوت\n\n{msg.caption}" if msg.caption else "🎵 رد من الإدارة بصوت"
            )

        else:
            await msg.reply_text("❌ نوع الرد غير مدعوم")
            return

        # إرسال تأكيد للمشرف
        await msg.reply_text("✅ تم إرسال الرد للمستخدم")

    except Exception as e:
        await msg.reply_text(f"❌ فشل إرسال الرد: {str(e)}")


# =====================
# أزرار الإدارة
# =====================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data.split("_")
    action = data[0]
    user_id = int(data[1])

    if action == "ban":
        cursor.execute(
            "UPDATE users SET banned=1 WHERE user_id=?",
            (user_id,)
        )
        conn.commit()
        await q.edit_message_text("🚫 تم حظر المستخدم")

    elif action == "info":
        cursor.execute(
            "SELECT username, first_name, messages_count FROM users WHERE user_id=?",
            (user_id,)
        )
        u = cursor.fetchone()

        if u:
            await q.message.reply_text(
                f"""
👤 **معلومات المستخدم**

🆔 **المعرف:** `{user_id}`
👤 **اليوزر:** @{u[0] if u[0] else 'لا يوجد'}
📛 **الاسم:** {u[1]}
💬 **عدد الرسائل:** {u[2]}
                """
            )
        else:
            await q.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات")


# =====================
# أوامر الإدارة
# =====================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages")
    msgs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned = cursor.fetchone()[0]

    await update.message.reply_text(
        f"""
📊 **إحصائيات البوت**

👥 **إجمالي المستخدمين:** {users}
💬 **إجمالي الرسائل:** {msgs}
🚫 **المحظورين:** {banned}
        """
    )


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    try:
        user_id = int(context.args[0])
        cursor.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم {user_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /unban user_id")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("❌ استخدم: /bd نص الرسالة أو رد على رسالة بالبث")
        return

    status_msg = await update.message.reply_text("🔄 جاري بدء البث...")

    cursor.execute("SELECT user_id FROM users WHERE banned = 0")
    users = cursor.fetchall()

    if not users:
        await status_msg.edit_text("❌ لا يوجد مستخدمين للبث")
        return

    success = 0
    failed = 0

    for user in users:
        user_id = user[0]
        try:
            if update.message.reply_to_message:
                replied = update.message.reply_to_message
                
                if replied.text:
                    await context.bot.send_message(chat_id=user_id, text=replied.text)
                elif replied.photo:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=replied.photo[-1].file_id,
                        caption=replied.caption
                    )
                elif replied.voice:
                    await context.bot.send_voice(
                        chat_id=user_id,
                        voice=replied.voice.file_id,
                        caption=replied.caption
                    )
                elif replied.video:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=replied.video.file_id,
                        caption=replied.caption
                    )
                elif replied.document:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=replied.document.file_id,
                        caption=replied.caption
                    )
                elif replied.sticker:
                    await context.bot.send_sticker(
                        chat_id=user_id,
                        sticker=replied.sticker.file_id
                    )
            else:
                broadcast_text = " ".join(context.args)
                await context.bot.send_message(chat_id=user_id, text=broadcast_text)
            
            success += 1
        except Exception as e:
            failed += 1
            print(f"فشل إرسال للمستخدم {user_id}: {e}")

    await status_msg.edit_text(
        f"✅ **تم البث بنجاح**\n\n"
        f"✓ تم الإرسال لـ: {success}\n"
        f"✗ فشل الإرسال لـ: {failed}"
    )


# =====================
# تشغيل البوت
# =====================

def main():
    print(f"✅ التوكن تم تحميله بنجاح: {BOT_TOKEN[:10]}...")
    print(f"✅ معرف المجموعة: {ADMIN_GROUP_ID}")
    
    app = Application.builder().token(BOT_TOKEN).build()

    # إضافة المعالجات
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, private_message))
    app.add_handler(MessageHandler(filters.Chat(ADMIN_GROUP_ID) & (~filters.COMMAND), admin_reply))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("bd", broadcast))

    print("🤖 البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
