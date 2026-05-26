"""Flask 서버 — API 엔드포인트 정의 및 분석 파이프라인 조율."""
import anthropic
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.metrics.pairwise import cosine_similarity

from database import init_db, save_emotion, save_training_sample, \
    get_calendar_data, get_diary_detail, get_weekly_records, \
    get_unfinished_dates, get_records_by_date, save_daily_diary, get_today_count, \
    get_weekly_diaries, delete_diary
from emotions import NLP_SCORE_TEMPLATE
from nlp import koelectra_classify
from llm import llm_only_analyze, llm_review_and_generate, get_book_recommendation, \
    chat_with_user, generate_daily_diary
from spotify_api import get_playlist
from books_api import fetch_book_info
from meditation import get_meditation
from config import get_api_key_1, get_api_key_2

app = Flask(__name__)
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data      = request.get_json()
    situation = data.get("situation", "").strip()
    thought   = data.get("thought", "").strip()
    feeling   = data.get("feeling", "").strip()

    if not any([situation, thought, feeling]):
        return jsonify({"error": "내용을 입력해주세요."}), 400
    if not get_api_key_1() or not get_api_key_2():
        return jsonify({"error": "설정 탭에서 Anthropic API 키 2개를 먼저 입력해주세요."}), 400

    combined_text = "\n".join(filter(None, [
        f"상황: {situation}" if situation else "",
        f"생각: {thought}"   if thought   else "",
        f"감정: {feeling}"   if feeling   else "",
    ]))

    try:
        # ── Step 1: KoELECTRA + LLM단독 병렬 실행 ───────────────────────────
        # KoELECTRA는 로컬 추론(무료), LLM단독은 토큰 비교용 API 호출
        with ThreadPoolExecutor(max_workers=2) as ex:
            nlp_future      = ex.submit(koelectra_classify, combined_text)
            llm_only_future = ex.submit(llm_only_analyze, situation, thought, feeling)

            nlp_dominant, nlp_confidence, nlp_scores = nlp_future.result()
            llm_only_result, llm_only_usage           = llm_only_future.result()

        # ── Step 2: LLM+NLP 검토 (KoELECTRA 결과 필요 → 순차 실행) ─────────
        reviewed, review_usage = llm_review_and_generate(
            situation, thought, feeling, nlp_dominant, nlp_scores
        )

        nlp_ok = reviewed.get("nlp_ok", True)
        print(f"[LLM 검토] nlp_ok={nlp_ok} | "
              f"{nlp_dominant} → {reviewed.get('dominant', nlp_dominant)}")

        if nlp_ok:
            final_dominant = nlp_dominant
            final_scores   = nlp_scores if nlp_scores else NLP_SCORE_TEMPLATE[nlp_dominant]
        else:
            final_dominant = reviewed.get("dominant", nlp_dominant)
            final_scores   = reviewed.get("scores", NLP_SCORE_TEMPLATE[final_dominant])

        # ── 파인튜닝 학습 데이터 저장 ─────────────────────────────────────────
        # 저장 조건: LLM이 수정했거나(불일치) / KoELECTRA 신뢰도 95% 미만(애매한 케이스)
        if nlp_dominant != final_dominant or nlp_confidence < 0.95:
            save_training_sample(combined_text, nlp_dominant, nlp_confidence, final_dominant)

        # ── Step 3: Spotify + Google Books 병렬 조회 ─────────────────────────
        book_title  = reviewed.get("book_title", "")
        book_author = reviewed.get("book_author", "")

        with ThreadPoolExecutor(max_workers=2) as ex:
            spotify_future = ex.submit(get_playlist, final_dominant)
            book_future    = ex.submit(fetch_book_info, book_title, book_author) \
                             if book_title else None

            playlist  = spotify_future.result()
            book_info = book_future.result() if book_future else None

        meditation = get_meditation(final_dominant)

        # ── 토큰 비교 계산 ────────────────────────────────────────────────────
        saved = llm_only_usage["total_tokens"] - review_usage["total_tokens"]
        token_comparison = {
            "llm_only": llm_only_usage,
            "llm_npn":  review_usage,
            "saved_tokens": saved,
            "saved_pct": round(saved / llm_only_usage["total_tokens"] * 100, 1)
                         if llm_only_usage["total_tokens"] > 0 else 0,
        }
        print(f"[토큰 비교] LLM단독={llm_only_usage['total_tokens']} / "
              f"LLM+NLP={review_usage['total_tokens']} / 절감={saved}")

        # ── LLM단독 vs NLP+LLM 유사도 계산 ──────────────────────────────────
        _EMOTION_KEYS = ["joy", "excitement", "neutral", "surprise",
                         "disgust", "fear", "sadness", "anger"]
        llm_scores = llm_only_result.get("scores", {})
        v1 = [float(llm_scores.get(k, 0)) for k in _EMOTION_KEYS]
        v2 = [float(final_scores.get(k, 0)) for k in _EMOTION_KEYS]
        cos_sim = float(cosine_similarity([v1], [v2])[0][0])
        similarity = {
            "dominant_match":       llm_only_result.get("dominant") == final_dominant,
            "score_similarity":     round(cos_sim, 4),
            "score_similarity_pct": round(cos_sim * 100, 1),
        }
        print(f"[유사도] dominant_match={similarity['dominant_match']} / "
              f"cosine={similarity['score_similarity_pct']}%")

        # ── 감정 기록 자동 저장 ────────────────────────────────────────────────
        today = datetime.now().strftime("%Y-%m-%d")
        save_emotion({
            "date":      today,
            "situation": situation,
            "thought":   thought,
            "feeling":   feeling,
            "diary_text": reviewed.get("diary_text", ""),
            "dominant":  final_dominant,
            **final_scores,
            "empathy":   reviewed.get("empathy", ""),
        })
        today_count = get_today_count()

        result = {
            **final_scores,
            "dominant":         final_dominant,
            "diary_text":       reviewed.get("diary_text", ""),
            "empathy":          reviewed.get("empathy", ""),
            "via_nlp":          nlp_ok,
            "nlp_confidence":   round(nlp_confidence * 100, 1),
            "playlist":         playlist["tracks"],
            "book_info":        book_info,
            "meditation":       meditation,
            "token_comparison": token_comparison,
            "similarity":       similarity,
            "today_count":      today_count,
        }
        return jsonify(result)

    except Exception as e:
        print(f"[분석 오류] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/save", methods=["POST"])
def save():
    data = request.get_json()
    data.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
    try:
        save_emotion(data)
        return jsonify({"status": "ok", "date": data["date"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/check-unfinished")
def check_unfinished():
    """
    미완성 일기(emotions 있으나 daily_diary 없는 과거 날짜) 자동 생성 엔드포인트.
    앱 초기화 시 호출 — 전날까지의 일기를 LLM으로 완성해 daily_diary에 저장.
    """
    _EMOTION_KEYS = ["joy", "excitement", "neutral", "surprise",
                     "disgust", "fear", "sadness", "anger"]
    dates    = get_unfinished_dates()
    finished = []

    for date in dates:
        try:
            records    = get_records_by_date(date)
            diary_text = generate_daily_diary(records)

            # 평균 점수 계산
            n          = len(records)
            avg_scores = {k: round(sum(r["scores"].get(k, 0) for r in records) / n, 1)
                          for k in _EMOTION_KEYS}
            dominant   = max(avg_scores, key=avg_scores.get)

            save_daily_diary(date, diary_text, dominant, avg_scores)
            finished.append(date)
            print(f"[미완성 일기] {date} → daily_diary 저장 완료")
        except Exception as e:
            print(f"[미완성 일기] {date} 처리 오류: {e}")

    return jsonify({"finished": finished, "count": len(finished)})


@app.route("/api/chat", methods=["POST"])
def chat():
    data     = request.get_json()
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"done": False, "message": "안녕하세요! 오늘 하루 어떠셨나요? 😊"})
    if not get_api_key_1() or not get_api_key_2():
        return jsonify({"error": "설정 탭에서 Anthropic API 키 2개를 먼저 입력해주세요."}), 400

    try:
        result = chat_with_user(messages)
        return jsonify(result)
    except anthropic.APIStatusError as e:
        if e.status_code == 529:
            print(f"[대화형] 529 과부하 — 사용자 안내 메시지 반환")
            return jsonify({"done": False,
                            "message": "서버가 잠시 바빠요 😢 조금 후에 다시 말씀해주세요!"})
        print(f"[대화형 오류] {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"[대화형 오류] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/calendar/<int:year>/<int:month>")
def calendar_data(year, month):
    return jsonify(get_calendar_data(year, month))


@app.route("/api/diary/<string:date>")
def diary_detail(date):
    record = get_diary_detail(date)
    if not record:
        return jsonify({"error": "기록 없음"}), 404
    return jsonify(record)


@app.route("/api/diary/<string:date>", methods=["DELETE"])
def diary_delete(date):
    try:
        delete_diary(date)
        return jsonify({"status": "ok", "date": date})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats/weekly")
def weekly_stats():
    # 차트용: 오늘 포함 7일 (emotions + daily_diary 혼합)
    records  = get_weekly_records(days=7)
    filled   = [r for r in records if r["record"] is not None]

    # 도서 추천용: daily_diary 완성 일기만 (오늘 제외)
    diaries   = get_weekly_diaries(days=7)
    book_info = None
    if len(diaries) >= 1:
        book_info = get_book_recommendation(diaries)

    return jsonify({
        "records":      records,
        "filled_count": len(filled),
        "diary_count":  len(diaries),   # 프론트 안내 메시지용
        "book_info":    book_info,
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  Emonote (리뉴얼) 시작!")
    print("  http://localhost:5000 에서 접속하세요")
    print("=" * 50)
    app.run(debug=True, port=5000)
