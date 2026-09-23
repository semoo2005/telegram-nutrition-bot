"""
وحدة الذكاء الاصطناعي (Gemini Vision & Text) لمدرب التغذية الشخصي.
تدعم كلاً من مكتبة google-genai ومكتبة google-generativeai مع التبديل التلقائي الذكي بين النماذج المتاحة.
"""

import os
import re
import logging
from typing import Tuple, Optional, List
from PIL import Image

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# فحص توفر المكتبات
USE_NEW_SDK = False
try:
    from google import genai
    from google.genai import types
    USE_NEW_SDK = True
except ImportError:
    try:
        import google.generativeai as legacy_genai
        if GEMINI_API_KEY:
            legacy_genai.configure(api_key=GEMINI_API_KEY)
    except ImportError:
        pass

SYSTEM_INSTRUCTION = """
أنت وكيل ذكي متعدِّد الوسائط (Multimodal AI Agent) وتعمل كمدرب تغذية شخصي عبر تطبيق التلجرام.

بيانات المستخدم الشخصية:
- الوزن الحالي: 73 كجم
- الهدف: خسارة 6 كجم خلال 3 أشهر (90 يوماً) للوصول إلى 67 كجم بتدرج آمن.
- الهدف اليومي للسعرات: 1,550 سعرة حرارية/يوم.

مهامك الرئيسية:
1. تحليل الصور: عند إرسال صورة وجبة، قم بتحليل مكوناتها، تقدير أحجام الحصص، وحساب إجمالي السعرات الحرارية والماكروز (بروتين، كربوهيدرات، دهون).
2. متابعة المتبقي: احتفظ بسجل السعرات لليوم الحالي، واطرح سعرات الوجبة الجديدة من المتبقي.
3. تقديم نصائح تدريجية: إذا اقترب المستخدم من إتمام سعراته اليومية (أو تجاوزها)، نبهه بلطف وقدم اقتراحات لوجبات خفيفة أو خطوات لليوم التالي.
4. إذا لم تكن الصورة واضحة، أو كان الطبق غامضاً، اسأل المستخدم بلطف لتوضيح المكونات مع إعطاء تقدير أولي.

صيغة الرد الإلزامية بعد كل تحليل وجبة:
-----------------------------------------
🍽️ **تحليل الوجبة:**
- [اسم المكون 1]: [الحجم التقديري] -> [عدد السعرات]
- [اسم المكون 2]: [الحجم التقديري] -> [عدد السعرات]

🔥 **مجموع الوجبة:** [X] سعرة حرارية

📊 **ملخص اليوم:**
- المستهلك اليوم: [Y] سعرة
- المتبقي لك اليوم: [المتبقي] سعرة حرارية

💡 **ملاحظة مدرب:** [نصيحة قصيرة ومشجعة ومرنة تناسب أهداف خسارة الوزن]
-----------------------------------------

هام جداً للبرمجة:
في نهاية الرد تماماً وفي سطر منفصل، اكتب الوسم التالي لمعرفة سعرات هذه الوجبة برمجياً:
[MEAL_CALORIES: X]
(حيث X هو رقم صحيح فقط يعبر عن مجموع سعرات هذه الوجبة).
"""

# قائمة النماذج المرشحة مع الأولوية للنموذج الأحدث
def get_candidate_models() -> List[str]:
    preferred = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    candidates = [preferred, "gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    # إزالة التكرار مع الحفاظ على الترتيب
    seen = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def parse_meal_calories(response_text: str) -> Tuple[str, int]:
    """استخراج رقم السعرات الحرارية وتنظيف النص المرسل للمستخدم."""
    calories = 0
    clean_text = response_text

    match_tag = re.search(r"\[MEAL_CALORIES:\s*(\d+)\]", response_text, re.IGNORECASE)
    if match_tag:
        calories = int(match_tag.group(1))
        clean_text = re.sub(r"\n?\[MEAL_CALORIES:\s*\d+\]", "", clean_text).strip()
    else:
        match_fallback = re.search(r"مجموع الوجبة[:\*]*\s*(\d+)", response_text)
        if match_fallback:
            calories = int(match_fallback.group(1))

    return clean_text, calories


def analyze_meal(
    image: Optional[Image.Image],
    text_prompt: str,
    consumed_today: int,
    daily_target: int = 1550
) -> Tuple[str, int]:
    """تحليل وجبة غذائية مع التبديل التلقائي بين النماذج في حال عدم توفر أحدها."""
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)

    context_prompt = f"""
معلومات اليوم الحالية للمستخدم:
- المستهلك حتى الآن قبل هذه الوجبة: {consumed_today} سعرة حرارية.
- الميزانية اليومية الكلية: {daily_target} سعرة حرارية.
- المتبقي قبل هذه الوجبة: {daily_target - consumed_today} سعرة حرارية.

المطلوب:
حلل الوجبة بدقة (احسب سعراتها X، ثم أضفها إلى المستهلك ليصبح Y = {consumed_today} + X، والمتبقي = {daily_target} - Y).
التزم تماماً بالصيغة المحددة في التعليمات.
وصف المستخدم أو تعليقه: {text_prompt if text_prompt else "لا يوجد تعليق إضافي"}
"""

    content_parts = [context_prompt]
    if image is not None:
        content_parts.append(image)

    models_to_try = get_candidate_models()
    last_error = None

    for model_name in models_to_try:
        try:
            if USE_NEW_SDK:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=content_parts,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION
                    )
                )
                text = response.text or ""
                return parse_meal_calories(text)
            else:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=api_key)
                model = legacy_genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=SYSTEM_INSTRUCTION
                )
                response = model.generate_content(content_parts)
                text = response.text or ""
                return parse_meal_calories(text)
        except Exception as e:
            logger.warning(f"Failed with model {model_name}: {e}")
            last_error = e
            continue

    return f"عذراً، حدث خطأ أثناء تحليل الوجبة: {str(last_error)}", 0


def coach_chat(user_message: str, consumed_today: int, daily_target: int = 1550) -> str:
    """الرد على استفسارات المستخدم كمدرب تغذية."""
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
    remaining = daily_target - consumed_today

    prompt = f"""
المستخدم يوجه لك سؤالاً أو رسالة كمدربه الشخصي:
رسالة المستخدم: "{user_message}"

سياق المستخدم لليوم:
- السعرات المستهلكة اليوم حتى الآن: {consumed_today} سعرة.
- السعرات المتبقية لليوم: {remaining} سعرة (من أصل {daily_target} سعرة).
- الهدف النهائي: 67 كجم (الوزن الحالي 73 كجم).

أجب بلطف، ومرونة، وتشجيع مع ربط إجابتك بهدفه والمتبقي له من السعرات اليوم إن كان ذلك مفيداً.
"""
    models_to_try = get_candidate_models()
    last_error = None

    for model_name in models_to_try:
        try:
            if USE_NEW_SDK:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION
                    )
                )
                return response.text or "أنا هنا لمساعدتك دائماً في رحلتك الغذائية!"
            else:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=api_key)
                model = legacy_genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=SYSTEM_INSTRUCTION
                )
                response = model.generate_content([prompt])
                return response.text or "أنا هنا لمساعدتك دائماً في رحلتك الغذائية!"
        except Exception as e:
            logger.warning(f"Chat failed with model {model_name}: {e}")
            last_error = e
            continue

    return f"عذراً، حدث خطأ: {str(last_error)}"
