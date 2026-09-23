"""
وحدة إدارة قاعدة البيانات (SQLite) لحفظ بيانات المستخدمين، والوجبات، ومتابعة السعرات اليومية.
"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, Any, List

DB_PATH = os.getenv("DB_PATH", "nutrition.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """تهيئة جداول قاعدة البيانات إذا لم تكن موجودة."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # جدول المستخدمين وملفاتهم الشخصية
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                current_weight REAL DEFAULT 73.0,
                target_weight REAL DEFAULT 67.0,
                daily_target INTEGER DEFAULT 1550,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول الوجبات المسجلة
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,       -- بصيغة YYYY-MM-DD للتجميع اليومي
                time TEXT,       -- بصيغة HH:MM
                meal_desc TEXT,
                calories INTEGER,
                protein REAL DEFAULT 0,
                carbs REAL DEFAULT 0,
                fat REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        conn.commit()


def ensure_user(user_id: int, current_weight: float = 73.0, target_weight: float = 67.0, daily_target: int = 1550):
    """التأكد من وجود المستخدم في قاعدة البيانات."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO users (user_id, current_weight, target_weight, daily_target)
                VALUES (?, ?, ?, ?)
            """, (user_id, current_weight, target_weight, daily_target))
            conn.commit()


def get_user(user_id: int) -> Dict[str, Any]:
    """جلب بيانات المستخدم."""
    ensure_user(user_id)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else {}


def add_meal(
    user_id: int,
    meal_desc: str,
    calories: int,
    protein: float = 0,
    carbs: float = 0,
    fat: float = 0
) -> int:
    """تسجيل وجبة جديدة للمستخدم في اليوم الحالي."""
    ensure_user(user_id)
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meals (user_id, date, time, meal_desc, calories, protein, carbs, fat)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, today_str, time_str, meal_desc, calories, protein, carbs, fat))
        conn.commit()
        return cursor.lastrowid


def get_today_summary(user_id: int) -> Dict[str, Any]:
    """
    حساب إجمالي السعرات المستهلكة والمتبقية لليوم.
    يتم التصفير التلقائي لأن الاستعلام يبحث فقط عن تاريخ اليوم الحالي YYYY-MM-DD.
    """
    user = get_user(user_id)
    daily_target = user.get("daily_target", 1550)
    today_str = datetime.now().strftime("%Y-%m-%d")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, time, meal_desc, calories, protein, carbs, fat
            FROM meals
            WHERE user_id = ? AND date = ?
            ORDER BY id ASC
        """, (user_id, today_str))
        rows = cursor.fetchall()
        meals = [dict(r) for r in rows]

    consumed = sum(m["calories"] for m in meals)
    remaining = daily_target - consumed

    return {
        "user_id": user_id,
        "date": today_str,
        "target": daily_target,
        "consumed": consumed,
        "remaining": remaining,
        "meals_count": len(meals),
        "meals": meals
    }


def reset_today(user_id: int):
    """إعادة تصفير وجبات اليوم الحالي للمستخدم يدوياً عند الطلب."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM meals
            WHERE user_id = ? AND date = ?
        """, (user_id, today_str))
        conn.commit()
