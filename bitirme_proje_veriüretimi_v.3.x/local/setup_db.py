"""
local/setup_db.py — PostgreSQL Index + Analiz Tablosu Kurulum Scripti

Çalıştırma (repo kökünden):
    python local/setup_db.py

.env dosyasındaki DATABASE_URL kullanılır.
Idempotent: IF NOT EXISTS — iki kez çalıştırılabilir.
"""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("ERROR: .env dosyasında DATABASE_URL tanımlı değil.")

engine = create_engine(DATABASE_URL)

# ─────────────────────────────────────────────────────────────────
# 1. PERFORMANS INDEX'LERİ (FK yerine — full table scan engeller)
# ─────────────────────────────────────────────────────────────────
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_log_userid      ON mdl_logstore_standard_log(userid);",
    "CREATE INDEX IF NOT EXISTS idx_log_course_time ON mdl_logstore_standard_log(courseid, timecreated);",
    "CREATE INDEX IF NOT EXISTS idx_grade_userid    ON mdl_grade_grades(userid, itemid);",
    "CREATE INDEX IF NOT EXISTS idx_qa_usage        ON mdl_question_attempts(questionusageid);",
    "CREATE INDEX IF NOT EXISTS idx_quizatt_user    ON mdl_quiz_attempts(userid, quiz);",
    "CREATE INDEX IF NOT EXISTS idx_completion_user ON mdl_course_modules_completion(userid, coursemoduleid);",
    "CREATE INDEX IF NOT EXISTS idx_assign_sub      ON mdl_assign_submission(userid, assignment);",
]

# ─────────────────────────────────────────────────────────────────
# 2. ANALİZ TABLOLARI (inference sonuçları)
# ─────────────────────────────────────────────────────────────────
TABLES = [
    """
    CREATE TABLE IF NOT EXISTS mdl_mimo_analysis (
        user_id          INTEGER PRIMARY KEY,
        risk_score       FLOAT   NOT NULL,
        risk_level       VARCHAR(10),
        predicted_grade  FLOAT   NOT NULL,
        model_confidence FLOAT,
        computed_at      TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS mdl_hkrt_analysis (
        id            SERIAL PRIMARY KEY,
        user_id       INTEGER      NOT NULL,
        topic_id      VARCHAR(100),
        resource_type VARCHAR(20),
        priority      INTEGER,
        reason_text   TEXT,
        computed_at   TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, topic_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS mdl_basic_values (
        user_id           INTEGER PRIMARY KEY,
        gpa               FLOAT,
        total_courses     INTEGER,
        completed_credits INTEGER,
        login_streak      INTEGER,
        updated_at        TIMESTAMP DEFAULT NOW()
    );
    """,
]

if __name__ == "__main__":
    with engine.connect() as conn:
        print("─── Index'ler oluşturuluyor ───")
        for sql in INDEXES:
            conn.execute(text(sql))
            print(f"  ✓ {sql.split('idx_')[1].split(' ')[0] if 'idx_' in sql else sql[:40]}")

        print("\n─── Analiz tabloları oluşturuluyor ───")
        for sql in TABLES:
            conn.execute(text(sql))
            tname = sql.split("TABLE IF NOT EXISTS ")[1].split(" (")[0].strip()
            print(f"  ✓ {tname}")

        conn.commit()

    print("\n✅ Kurulum tamamlandı.")
