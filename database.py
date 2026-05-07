"""SQLite DB 초기화·CRUD·마이그레이션 — emotions / training_data / daily_diary 테이블 관리."""
import json
import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH
from emotions import EMOTIONS, EN_TO_KO

_EMOTION_KEYS = ["joy", "excitement", "neutral", "surprise",
                 "disgust", "fear", "sadness", "anger"]


# ── 마이그레이션 ───────────────────────────────────────────────────────────────
def migrate_db() -> None:
    """
    스키마 마이그레이션: 기존 DB를 새 스키마에 맞게 안전하게 업그레이드.
      - emotions.date UNIQUE 제약 제거 (하루 여러 번 저장 허용)
      - emotions.recorded_at 컬럼 추가
      - daily_diary 테이블 생성
    """
    conn = sqlite3.connect(DB_PATH)

    # ── emotions.date UNIQUE 제거: 구 스키마 감지 후 테이블 재생성 ─────────────
    schema_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='emotions'"
    ).fetchone()
    if schema_row and "UNIQUE" in schema_row[0].upper():
        print("[DB 마이그레이션] emotions.date UNIQUE 제약 제거 시작")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emotions_new (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
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
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO emotions_new
                (id, date, situation, thought, feeling, diary_text, dominant,
                 joy, excitement, neutral, surprise, disgust, fear, sadness, anger, empathy)
            SELECT id, date, situation, thought, feeling, diary_text, dominant,
                   joy, excitement, neutral, surprise, disgust, fear, sadness, anger, empathy
            FROM emotions
        """)
        conn.execute("DROP TABLE emotions")
        conn.execute("ALTER TABLE emotions_new RENAME TO emotions")
        print("[DB 마이그레이션] emotions 테이블 재생성 완료")

    # ── emotions.recorded_at 컬럼 추가 (구 스키마 대응) ──────────────────────
    try:
        conn.execute(
            "ALTER TABLE emotions ADD COLUMN recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )
        print("[DB 마이그레이션] emotions.recorded_at 추가 완료")
    except sqlite3.OperationalError:
        pass  # 이미 존재

    # ── daily_diary 테이블 생성 (없으면) ─────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_diary (
            date       TEXT UNIQUE NOT NULL,
            diary_text TEXT,
            dominant   TEXT,
            scores     TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ── DB 초기화 ──────────────────────────────────────────────────────────────────
def init_db() -> None:
    """DB 파일 생성 및 테이블 초기화. 앱 시작 시 1회 호출."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emotions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
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
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_diary (
            date       TEXT UNIQUE NOT NULL,
            diary_text TEXT,
            dominant   TEXT,
            scores     TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    migrate_db()  # 구 스키마 업그레이드 적용


# ── 감정 기록 저장 (하루 여러 번 저장 가능) ────────────────────────────────────
def save_emotion(data: dict) -> None:
    """감정 분석 결과 1건 저장. date UNIQUE 없음 → 하루 N번 저장 가능."""
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO emotions
              (date, situation, thought, feeling, diary_text, dominant,
               joy, excitement, neutral, surprise, disgust, fear, sadness, anger, empathy)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            date,
            data.get("situation", ""), data.get("thought",  ""), data.get("feeling", ""),
            data.get("diary_text", ""), data.get("dominant", "neutral"),
            data.get("joy", 0),        data.get("excitement", 0), data.get("neutral", 0),
            data.get("surprise", 0),   data.get("disgust", 0),    data.get("fear", 0),
            data.get("sadness", 0),    data.get("anger", 0),      data.get("empathy", ""),
        ))
        conn.commit()
    finally:
        conn.close()


def get_today_count() -> int:
    """오늘 날짜에 저장된 emotions 기록 수 반환."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn  = sqlite3.connect(DB_PATH)
    count = conn.execute(
        "SELECT COUNT(*) FROM emotions WHERE date=?", (today,)
    ).fetchone()[0]
    conn.close()
    return count


# ── 미완성 일기 관련 ────────────────────────────────────────────────────────────
def get_unfinished_dates() -> list:
    """
    emotions 기록은 있으나 daily_diary 미완성인 오늘 이전 날짜 목록 반환 (오름차순).
    자동 일기 생성 대상을 찾을 때 사용.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    conn  = sqlite3.connect(DB_PATH)
    rows  = conn.execute("""
        SELECT DISTINCT date FROM emotions
        WHERE date < ?
          AND date NOT IN (SELECT date FROM daily_diary)
        ORDER BY date
    """, (today,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_records_by_date(date: str) -> list:
    """특정 날짜의 emotions 기록 전체 반환 (recorded_at 오름차순)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT situation, thought, feeling, diary_text, dominant,
               joy, excitement, neutral, surprise, disgust, fear, sadness, anger,
               empathy, recorded_at
        FROM emotions WHERE date=? ORDER BY recorded_at
    """, (date,)).fetchall()
    conn.close()
    return [{
        "situation":  r[0] or "", "thought":  r[1] or "", "feeling":    r[2] or "",
        "diary_text": r[3] or "", "dominant": r[4],
        "scores": {
            "joy": r[5], "excitement": r[6], "neutral":  r[7], "surprise": r[8],
            "disgust": r[9], "fear": r[10], "sadness": r[11], "anger":   r[12],
        },
        "empathy":     r[13] or "",
        "recorded_at": r[14] or "",
    } for r in rows]


def save_daily_diary(date: str, diary_text: str, dominant: str, scores: dict) -> None:
    """daily_diary 테이블에 날짜별 완성 일기 저장. 이미 있으면 덮어쓰기."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO daily_diary (date, diary_text, dominant, scores)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                diary_text=excluded.diary_text,
                dominant=excluded.dominant,
                scores=excluded.scores
        """, (date, diary_text, dominant, json.dumps(scores, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


# ── 달력 / 상세 조회 ────────────────────────────────────────────────────────────
def get_calendar_data(year: int, month: int) -> dict:
    """
    월별 달력 데이터 반환.
      - 과거 날짜: daily_diary 기준
      - 오늘: emotions 최근 기록 기준
    """
    prefix = f"{year}-{str(month).zfill(2)}"
    today  = datetime.now().strftime("%Y-%m-%d")
    conn   = sqlite3.connect(DB_PATH)

    # 과거: daily_diary
    diary_rows = conn.execute(
        "SELECT date, dominant FROM daily_diary WHERE date LIKE ? AND date < ?",
        (f"{prefix}%", today),
    ).fetchall()

    # 오늘: emotions 가장 최근 감정
    today_row = None
    if today.startswith(prefix):
        row = conn.execute(
            "SELECT dominant FROM emotions WHERE date=? ORDER BY recorded_at DESC LIMIT 1",
            (today,),
        ).fetchone()
        if row:
            today_row = (today, row[0])

    conn.close()
    result = {r[0]: {"dominant": r[1]} for r in diary_rows}
    if today_row:
        result[today_row[0]] = {"dominant": today_row[1], "is_today": True}
    return result


def get_diary_detail(date: str) -> dict | None:
    """
    날짜 상세 조회.
      - 오늘: emotions 기록 목록 반환 (is_today=True)
      - 과거: daily_diary 반환 (is_today=False)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    conn  = sqlite3.connect(DB_PATH)

    if date == today:
        rows = conn.execute("""
            SELECT situation, thought, feeling, diary_text, dominant,
                   joy, excitement, neutral, surprise, disgust, fear, sadness, anger,
                   empathy, recorded_at
            FROM emotions WHERE date=? ORDER BY recorded_at
        """, (date,)).fetchall()
        conn.close()
        if not rows:
            return None
        records = [{
            "situation":  r[0] or "", "thought":  r[1] or "", "feeling":    r[2] or "",
            "diary_text": r[3] or "", "dominant": r[4],
            "scores": {"joy": r[5], "excitement": r[6], "neutral": r[7], "surprise": r[8],
                       "disgust": r[9], "fear": r[10], "sadness": r[11], "anger": r[12]},
            "empathy":     r[13] or "",
            "recorded_at": r[14] or "",
        } for r in rows]
        return {
            "date":     date,
            "is_today": True,
            "records":  records,
            "dominant": records[-1]["dominant"],  # 마지막 기록 감정 대표
        }

    # 과거: daily_diary
    row = conn.execute(
        "SELECT diary_text, dominant, scores FROM daily_diary WHERE date=?", (date,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    scores = json.loads(row[2]) if row[2] else {}
    return {
        "date":       date,
        "is_today":   False,
        "diary_text": row[0] or "",
        "dominant":   row[1],
        "scores":     scores,
    }


# ── 주간 통계 ──────────────────────────────────────────────────────────────────
def get_weekly_records(days: int = 7) -> list:
    """
    최근 N일 감정 기록 반환.
      - 과거 날짜: daily_diary (하루 평균 점수)
      - 오늘: emotions 집계 (실시간 평균)
    """
    today   = datetime.now().strftime("%Y-%m-%d")
    records = []
    conn    = sqlite3.connect(DB_PATH)

    for i in range(days - 1, -1, -1):
        d   = datetime.now() - timedelta(days=i)
        key = d.strftime("%Y-%m-%d")

        if key == today:
            # 오늘: emotions 집계
            rows = conn.execute(
                "SELECT dominant, joy, excitement, neutral, surprise, "
                "disgust, fear, sadness, anger FROM emotions WHERE date=?", (key,)
            ).fetchall()
            if rows:
                n   = len(rows)
                avg = {k: round(sum(r[i + 1] for r in rows) / n, 1)
                       for i, k in enumerate(_EMOTION_KEYS)}
                record_data = {
                    "dominant":   max(avg, key=avg.get),
                    "scores":     avg,
                    "diary_text": "",
                }
            else:
                record_data = None
        else:
            # 과거: daily_diary
            row = conn.execute(
                "SELECT dominant, scores, diary_text FROM daily_diary WHERE date=?", (key,)
            ).fetchone()
            if row:
                scores = json.loads(row[1]) if row[1] else {}
                record_data = {"dominant": row[0], "scores": scores, "diary_text": row[2] or ""}
            else:
                record_data = None

        records.append({
            "date":    key,
            "weekday": ["월", "화", "수", "목", "금", "토", "일"][d.weekday()],
            "record":  record_data,
        })

    conn.close()
    return records


# ── 주간 도서 추천용 daily_diary 조회 ──────────────────────────────────────────
def get_weekly_diaries(days: int = 7) -> list:
    """
    daily_diary 테이블에서 최근 N일치 완성 일기 반환 (오름차순).
    오늘 날짜는 포함하지 않음 (당일 일기는 자정 이후 생성).
    7일 미만이면 있는 것만 반환.

    Returns:
        [{"date": "YYYY-MM-DD", "diary_text": "...", "dominant": "...", "scores": {...}}, ...]
    """
    today  = datetime.now().strftime("%Y-%m-%d")
    since  = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn   = sqlite3.connect(DB_PATH)
    rows   = conn.execute("""
        SELECT date, diary_text, dominant, scores
        FROM daily_diary
        WHERE date >= ? AND date < ?
        ORDER BY date ASC
    """, (since, today)).fetchall()
    conn.close()
    return [
        {
            "date":       r[0],
            "diary_text": r[1] or "",
            "dominant":   r[2],
            "scores":     json.loads(r[3]) if r[3] else {},
        }
        for r in rows
    ]


# ── 학습 데이터 ────────────────────────────────────────────────────────────────
def save_training_sample(diary_text: str, nlp_dominant: str,
                         nlp_confidence: float, llm_dominant: str) -> None:
    """KoELECTRA vs LLM 불일치 케이스를 파인튜닝 학습 데이터로 저장."""
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


def get_recent_emotion_history(days: int = 7) -> str:
    """최근 N일 감정 기록을 텍스트로 반환 (LLM 컨텍스트용)."""
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
