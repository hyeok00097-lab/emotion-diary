from flask import Flask, request, jsonify, render_template
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.metrics.pairwise import cosine_similarity

from database import init_db, save_emotion, save_training_sample, \
    get_calendar_data, get_diary_detail, get_weekly_records
from emotions import NLP_SCORE_TEMPLATE
from nlp import koelectra_classify
from llm import llm_only_analyze, llm_review_and_generate, get_book_recommendation
from spotify_api import get_playlist
from books_api import fetch_book_info
from meditation import get_meditation
from config import save_api_keys, get_keys_status, get_api_key_1, get_api_key_2

app = Flask(__name__)
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(get_keys_status())


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json()
    key1 = data.get("key1", "").strip()
    key2 = data.get("key2", "").strip()
    if not key1 or not key2:
        return jsonify({"error": "두 API 키를 모두 입력해주세요."}), 400
    try:
        save_api_keys(key1, key2)
        print(f"[설정] API 키 업데이트 완료")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

        result = {
            **final_scores,
            "dominant":         final_dominant,
            "diary_text":       reviewed.get("diary_text", ""),
            "summary":          reviewed.get("summary", ""),
            "empathy":          reviewed.get("empathy", ""),
            "via_nlp":          nlp_ok,
            "nlp_confidence":   round(nlp_confidence * 100, 1),
            "playlist":         playlist["tracks"],
            "book_info":        book_info,
            "meditation":       meditation,
            "token_comparison": token_comparison,
            "similarity":       similarity,
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


@app.route("/api/calendar/<int:year>/<int:month>")
def calendar_data(year, month):
    return jsonify(get_calendar_data(year, month))


@app.route("/api/diary/<string:date>")
def diary_detail(date):
    record = get_diary_detail(date)
    if not record:
        return jsonify({"error": "기록 없음"}), 404
    return jsonify(record)


@app.route("/api/stats/weekly")
def weekly_stats():
    records   = get_weekly_records(days=7)
    filled    = [r for r in records if r["record"] is not None]
    book_info = None

    if len(filled) >= 7:
        dominant_week = max(
            {r["record"]["dominant"] for r in filled},
            key=lambda e: sum(1 for r in filled if r["record"]["dominant"] == e),
        )
        book_info = get_book_recommendation(dominant_week, filled)

    return jsonify({
        "records":      records,
        "filled_count": len(filled),
        "book_info":    book_info,
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  Emonote (리뉴얼) 시작!")
    print("  http://localhost:5000 에서 접속하세요")
    print("=" * 50)
    app.run(debug=True, port=5000)
