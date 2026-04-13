import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH
from emotions import EMOTIONS, EN_TO_KO


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emotions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT UNIQUE NOT NULL,
            situation   TEXT,
            thought     TEXT,
            feeling     TEXT,
            diary_text  TEXT,
            dominant    TEXT NOT NULL,
            joy         REAL DEFAULT 0,
            excitement  REAL DEFAULT 0,
            neutral     REAL DEFAULT 0,
            surprise    REAL DEFAULT 0,
            disgust     REAL DEFAULT 0,
            fear        REAL DEFAULT 0,
            sadness     REAL DEFAULT 0,
            anger       REAL DEFAULT 0,
            empathy     TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS training_data (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            diary_text      TEXT NOT NULL,
            nlp_dominant    TEXT NOT NULL,
            nlp_confidence  REAL DEFAULT 0,
            llm_dominant    TEXT NOT NULL,
            llm_corrected   INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.close()


def save_emotion(data: dict) -> None:
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO emotions
              (date, situation, thought, feeling, diary_text, dominant,
               joy, excitement, neutral, surprise, disgust, fear, sadness, anger, empathy)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(date) DO UPDATE SET
                situation=excluded.situation, thought=excluded.thought,
                feeling=excluded.feeling, diary_text=excluded.diary_text,
                dominant=excluded.dominant,
                joy=excluded.joy, excitement=excluded.excitement,
                neutral=excluded.neutral, surprise=excluded.surprise,
                disgust=excluded.disgust, fear=excluded.fear,
                sadness=excluded.sadness, anger=excluded.anger,
                empathy=excluded.empathy
        """, (
            date,
            data.get("situation", ""), data.get("thought", ""), data.get("feeling", ""),
            data.get("diary_text", ""), data.get("dominant", "neutral"),
            data.get("joy", 0), data.get("excitement", 0), data.get("neutral", 0),
            data.get("surprise", 0), data.get("disgust", 0), data.get("fear", 0),
            data.get("sadness", 0), data.get("anger", 0), data.get("empathy", ""),
        ))
        conn.commit()
    finally:
        conn.close()


def save_training_sample(diary_text: str, nlp_dominant: str,
                         nlp_confidence: float, llm_dominant: str) -> None:
    llm_corrected = 1 if nlp_dominant != llm_dominant else 0
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO training_data
              (diary_text, nlp_dominant, nlp_confidence, llm_dominant, llm_corrected)
            VALUES (?, ?, ?, ?, ?)
        """, (diary_text, nlp_dominant, nlp_confidence, llm_dominant, llm_corrected))
        conn.commit()
        print(f"[학습데이터] NLP:{nlp_dominant} → LLM:{llm_dominant} | corrected={llm_corrected}")
    except Exception as e:
        print(f"[학습데이터] 저장 실패: {e}")
    finally:
        conn.close()


def get_calendar_data(year: int, month: int) -> dict:
    prefix = f"{year}-{str(month).zfill(2)}"
    conn   = sqlite3.connect(DB_PATH)
    rows   = conn.execute(
        "SELECT date, dominant FROM emotions WHERE date LIKE ?", (f"{prefix}%",)
    ).fetchall()
    conn.close()
    return {r[0]: {"dominant": r[1]} for r in rows}


def get_diary_detail(date: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT situation, thought, feeling, diary_text, dominant, "
        "joy, excitement, neutral, surprise, disgust, fear, sadness, anger, empathy "
        "FROM emotions WHERE date=?", (date,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "date":       date,
        "situation":  row[0] or "",
        "thought":    row[1] or "",
        "feeling":    row[2] or "",
        "diary_text": row[3] or "",
        "dominant":   row[4],
        "scores": {
            "joy": row[5], "excitement": row[6], "neutral": row[7],
            "surprise": row[8], "disgust": row[9], "fear": row[10],
            "sadness": row[11], "anger": row[12],
        },
        "empathy": row[13] or "",
    }


def get_weekly_records(days: int = 7) -> list:
    today   = datetime.now()
    records = []
    conn    = sqlite3.connect(DB_PATH)
    for i in range(days - 1, -1, -1):
        d   = today - timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT dominant, joy, excitement, neutral, surprise, "
            "disgust, fear, sadness, anger, diary_text FROM emotions WHERE date=?", (key,)
        ).fetchone()
        records.append({
            "date":    key,
            "weekday": ["월", "화", "수", "목", "금", "토", "일"][d.weekday()],
            "record":  {
                "dominant":   row[0],
                "scores":     {"joy": row[1], "excitement": row[2], "neutral": row[3],
                               "surprise": row[4], "disgust": row[5], "fear": row[6],
                               "sadness": row[7], "anger": row[8]},
                "diary_text": row[9] or "",
            } if row else None,
        })
    conn.close()
    return records


def get_recent_emotion_history(days: int = 7) -> str:
    conn  = sqlite3.connect(DB_PATH)
    today = datetime.now()
    rows  = []
    for i in range(days, 0, -1):
        d   = today - timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        row = conn.execute("SELECT dominant FROM emotions WHERE date=?", (key,)).fetchone()
        if row:
            rows.append(f"{key}: {EN_TO_KO.get(row[0], row[0])}")
    conn.close()
    return ("최근 감정 기록:\n" + "\n".join(rows)) if rows else ""
