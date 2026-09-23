"""
الملف الرئيسي لتشغيل بوت تلجرام لمدرب التغذية الشخصي الذكي.
"""

import os
import io
import logging
from dotenv import load_dotenv
from PIL import Image

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# تحميل المتغيرات من ملف .env
load_dotenv()

import database
import ai_coach

# ضبط السجلات (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الترحيب بالمستخدم وعرض الملف الشخصي الحالي والهدف."""
    user = update.effective_user
    user_id = user.id
    database.ensure_user(user_id)
    summary = database.get_today_summary(user_id)

    welcome_message = (
        f"أهلاً بك يا {user.first_name}! 🥗💪\n"
        f"أنا مدربك الشخصي الذكي للتغذية على تلجرام.\n\n"
        f"🎯 **ملفك الشخصي والهدف:**\n"
        f"• الوزن الحالي: 73 كجم\n"
        f"• الوزن المستهدف: 67 كجم (خسارة 6 كجم خلال 90 يوماً بتدرج آمن)\n"
        f"• الميزانية اليومية: {summary['target']:,} سعرة حرارية/يوم\n\n"
        f"📊 **حالة اليوم:**\n"
        f"• المستهلك اليوم: {summary['consumed']:,} سعرة\n"
        f"• المتبقي لك اليوم: {summary['remaining']:,} سعرة حرارية\n\n"
        f"📸 **كيف تستخدمني؟**\n"
        f"1. التقط أو أرسل صورة أي وجبة أو سناك.\n"
        f"2. أو اكتب ما أكلته نصياً (مثل: 'أكلت 2 بيضة مسلوقة وتفاحة').\n"
        f"3. سأحلل المكونات والسعرات والماكروز فوراً وأطرحها من رصيدك اليومي!\n\n"
        f"💡 **أوامر سريعة:**\n"
        f"/status - لمعرفة رصيدك المتبقي ووجبات اليوم\n"
        f"/reset - لتصفير عداد اليوم والبدء من جديد\n"
        f"/help - لشرح التعليمات"
    )
    await update.message.reply_text(welcome_message)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات وسجل اليوم للمستخدم."""
    user_id = update.effective_user.id
    summary = database.get_today_summary(user_id)

    meals_text = ""
    if summary["meals"]:
        meals_text = "\n\n📋 **وجباتك المسجلة اليوم:**\n"
        for idx, m in enumerate(summary["meals"], 1):
            desc = m["meal_desc"] if m["meal_desc"] else "وجبة مصورة"
            meals_text += f"{idx}. [{m['time']}] {desc} -> {m['calories']} سعرة\n"
    else:
        meals_text = "\n\nلم تسجل أي وجبة بعد لليوم. رصيدك كامل جاهز! 🌟"

    status_message = (
        f"📊 **ملخص يومك حتى الآن ({summary['date']}):**\n"
        f"• المستهلك اليوم: {summary['consumed']:,} سعرة\n"
        f"• المتبقي لك اليوم: {summary['remaining']:,} سعرة حرارية (من أصل {summary['target']:,})\n"
        f"{meals_text}\n"
        f"💡 استمر بنفس العزيمة، كل وجبة محسوبة تقربك من هدف الـ 67 كجم!"
    )
    await update.message.reply_text(status_message)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تصفير سجل اليوم يدوياً."""
    user_id = update.effective_user.id
    database.reset_today(user_id)
    summary = database.get_today_summary(user_id)

    await update.message.reply_text(
        f"🔄 **تم تصفير عداد اليوم بنجاح!**\n\n"
        f"رصيدك المتاح الآن: **{summary['target']:,} سعرة حرارية**.\n"
        f"أنا جاهز لاستقبال وجبتك القادمة! 🍏"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة والتعليمات."""
    help_text = (
        "💡 **دليل استخدام مدرب التغذية:**\n\n"
        "• **تصوير الوجبات:** كل ما عليك هو إرسال صورة صحنك أو وجبتك، وسأقوم بتقدير الحجم وحساب السعرات والماكروز تلقائياً.\n"
        "• **إضافة تعليق للصورة:** يمكنك كتابة توضيح مع الصورة (مثلاً: 'بدون زيت' أو 'خبز بر').\n"
        "• **التسجيل النصي:** يمكنك كتابة ما أكلته دون صورة إذا لم تتمكن من التصوير.\n"
        "• **الاستشارة:** اسألني أي سؤال عن التغذية وسأجيبك فوراً بما يناسب هدفك.\n"
        "• **التصفير التلقائي:** يتم تصفير السعرات تلقائياً كل ليلة عند بدء يوم جديد.\n\n"
        "الأوامر:\n"
        "/start - البداية والترحيب\n"
        "/status - رصيد اليوم المتبقي وقائمة الوجبات\n"
        "/reset - تصفير عداد اليوم يدوياً"
    )
    await update.message.reply_text(help_text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الصور الواردة للوجبات."""
    user_id = update.effective_user.id
    photo = update.message.photo[-1]  # أخذ أعلى دقة للصورة
    caption = update.message.caption or ""

    # إظهار حالة جاري المعالجة
    await update.message.chat.send_action(action=ChatAction.TYPING)
    loading_msg = await update.message.reply_text("جاري فحص الوجبة وتحليل المكونات والسعرات بالذكاء الاصطناعي... 🥗🔍")

    try:
        # تنزيل ملف الصورة إلى الذاكرة
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        image = Image.open(io.BytesIO(photo_bytes))

        # جلب المستهلك لليوم
        summary = database.get_today_summary(user_id)
        consumed_today = summary["consumed"]
        target = summary["target"]

        # تحليل الوجبة عبر الذكاء الاصطناعي
        reply_text, meal_calories = ai_coach.analyze_meal(
            image=image,
            text_prompt=caption,
            consumed_today=consumed_today,
            daily_target=target
        )

        # تسجيل الوجبة في قاعدة البيانات إذا تم استخراج سعرات
        if meal_calories > 0:
            meal_desc = caption.strip() if caption.strip() else "وجبة مصورة"
            database.add_meal(user_id, meal_desc, meal_calories)

        # حذف رسالة الانتظار وإرسال التحليل النهائي
        await loading_msg.delete()
        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Error analyzing photo: {e}")
        await loading_msg.edit_text("عذراً، تعذر تحليل الصورة، يرجى المحاولة مرة أخرى أو توضيح المكونات نصياً.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية سواء كانت تسجيلاً لوجبة أو استشارة للمدرب."""
    user_id = update.effective_user.id
    user_text = update.message.text.strip()
    if not user_text:
        return

    await update.message.chat.send_action(action=ChatAction.TYPING)
    summary = database.get_today_summary(user_id)
    consumed_today = summary["consumed"]
    target = summary["target"]

    # الكلمات المفتاحية التي تدل على تسجيل وجبة
    food_keywords = [
        "أكلت", "اكلت", "تناولت", "وجبة", "فطور", "غداء", "عشاء",
        "سناك", "شربت", "صحن", "كوب", "تفاح", "موز", "دجاج", "لحم",
        "بيض", "أرز", "رز", "خبز", "بروتين", "سعرة", "جرام"
    ]

    is_meal_log = any(kw in user_text.lower() for kw in food_keywords)

    if is_meal_log:
        # التعامل معها كوجبة نصية وحساب سعراتها
        reply_text, meal_calories = ai_coach.analyze_meal(
            image=None,
            text_prompt=user_text,
            consumed_today=consumed_today,
            daily_target=target
        )
        if meal_calories > 0:
            database.add_meal(user_id, user_text, meal_calories)
        await update.message.reply_text(reply_text)
    else:
        # الرد كمدرب وتقديم نصائح واستشارات
        coach_response = ai_coach.coach_chat(
            user_message=user_text,
            consumed_today=consumed_today,
            daily_target=target
        )
        await update.message.reply_text(coach_response)


def main():
    """نقطة تشغيل البوت."""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ خطأ: لم يتم ضبط TELEGRAM_BOT_TOKEN في ملف .env!")
        print("يرجى إنشاء ملف .env ووضع التوكن الخاص ببوتك.")
        return

    if not GEMINI_API_KEY:
        print("❌ خطأ: لم يتم ضبط GEMINI_API_KEY في ملف .env!")
        print("يرجى الحصول على مفتاح مجاني من https://aistudio.google.com/")
        return

    # تهيئة قاعدة البيانات
    database.init_db()
    print("✅ تم تجهيز قاعدة البيانات بنجاح.")

    # بناء وتشغيل تطبيق تلجرام
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("help", help_command))

    # تسجيل معالجات الوسائط والرسائل
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # تشغيل خادم ويب مصغر في الخلفية للتوافق مع استضافات الويب المجانية (مثل Render Web Service)
    def run_health_server():
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Bot is healthy and running!")

            def log_message(self, format, *args):
                pass  # تجاهل سجلات الوصول للحفاظ على نظافة الـ logs

        port = int(os.getenv("PORT", 8080))
        try:
            server = HTTPServer(("0.0.0.0", port), HealthHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            print(f"🌐 تم تشغيل خادم المراقبة على المنفذ {port}")
        except Exception as e:
            print(f"تنبيه خادم المراقبة: {e}")

    run_health_server()

    print("🚀 بوت مدرب التغذية الذكي قيد التشغيل الآن على تلجرام...")
    app.run_polling()


if __name__ == "__main__":
    main()

