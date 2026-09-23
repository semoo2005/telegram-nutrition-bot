"""
اختبار تحقق سريع لوحدة قاعدة البيانات والحسابات اليومية.
"""

import os
import database

def test_database():
    print("--- بدء فحص قاعدة البيانات ---")
    os.environ["DB_PATH"] = "test_nutrition.db"
    
    # تنظيف أي ملف اختبار قديم
    if os.path.exists("test_nutrition.db"):
        os.remove("test_nutrition.db")
        
    database.init_db()
    user_id = 99999
    
    # 1. التأكد من إنشاء المستخدم والهدف اليومي الافتراضي
    database.ensure_user(user_id)
    summary = database.get_today_summary(user_id)
    assert summary["consumed"] == 0, f"المتوقع 0 ولكن وجد {summary['consumed']}"
    assert summary["remaining"] == 1550, f"المتوقع 1550 ولكن وجد {summary['remaining']}"
    print("✅ فحص التهيئة والتصفير اليومي: ناجح")
    
    # 2. إضافة وجبة أولى (إفطار: 400 سعرة)
    database.add_meal(user_id, "بيض مسلوق وشوفان", 400, protein=25, carbs=45, fat=12)
    summary = database.get_today_summary(user_id)
    assert summary["consumed"] == 400
    assert summary["remaining"] == 1150
    assert len(summary["meals"]) == 1
    print("✅ فحص تسجيل الوجبة الأولى وخصم السعرات: ناجح")
    
    # 3. إضافة وجبة ثانية (غداء: 650 سعرة)
    database.add_meal(user_id, "صدر دجاج مشوي مع أرز وسلطة", 650, protein=50, carbs=60, fat=15)
    summary = database.get_today_summary(user_id)
    assert summary["consumed"] == 1050
    assert summary["remaining"] == 500
    assert len(summary["meals"]) == 2
    print("✅ فحص تراكم الوجبات وتحديث المتبقي: ناجح")
    
    # 4. فحص التصفير اليدوي
    database.reset_today(user_id)
    summary = database.get_today_summary(user_id)
    assert summary["consumed"] == 0
    assert summary["remaining"] == 1550
    assert len(summary["meals"]) == 0
    print("✅ فحص أمر التصفير /reset: ناجح")
    
    # إزالة ملف الاختبار
    if os.path.exists("test_nutrition.db"):
        os.remove("test_nutrition.db")
        
    print("🎉 جميع اختبارات قاعدة البيانات والتتبع تمت بنجاح تام!")

if __name__ == "__main__":
    test_database()
