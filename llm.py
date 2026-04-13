import json
import anthropic
from config import get_api_key_1, get_api_key_2
from emotions import EN_TO_KO, NLP_SCORE_TEMPLATE, EMOTIONS
from books_api import fetch_book_info

# 키는 호출 시마다 최신 값을 읽어 클라이언트 생성 (설정 UI 즉시 반영)
def _client1() -> anthropic.Anthropic:
    """LLM 단독 분석용 클라이언트 (API 키 1)."""
    return anthropic.Anthropic(api_key=get_api_key_1())

def _client2() -> anthropic.Anthropic:
    """LLM+NLP 검토용 클라이언트 (API 키 2)."""
    return anthropic.Anthropic(api_key=get_api_key_2())


# ── 토큰 사용량 딕셔너리 헬퍼 ────────────────────────────────────────────────
def _usage(message) -> dict:
    return {
        "input_tokens":  message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "total_tokens":  message.usage.input_tokens + message.usage.output_tokens,
    }


# ── LLM 단독 분석 (NLP 없이 Claude가 전부 처리) ──────────────────────────────
def llm_only_analyze(
    situation: str, thought: str, feeling: str,
) -> tuple[dict, dict]:
    """
    KoELECTRA 없이 LLM이 감정 분류부터 추천까지 전부 수행.
    토큰 사용량 비교 전용 — 결과는 DB에 저장하지 않음.
    반환: (result_dict, token_usage_dict)
    """
    prompt = f"""당신은 감정 일기 분석 전문가입니다.

[STF 감정 기록]
상황(Situation): {situation}
생각(Thought):   {thought}
감정(Feeling):   {feeling}

위 STF 기록을 분석하여 아래 8가지 감정 중 가장 지배적인 하나를 선택하고,
각 감정의 비율(합계=100), 감정 요약, 공감, 도서 추천을 JSON으로만 반환하세요.
다른 텍스트 없이 JSON만 출력하세요.

감정 8종: joy(기쁨), excitement(설렘), neutral(평범함), surprise(놀라움),
          disgust(불쾌함), fear(두려움), sadness(슬픔), anger(분노)

[diary_text 작성 지침]
- 1인칭 구어체로 작성 (너무 문학적이거나 격식체 금지)
- "오늘 ~했다" 형식으로 시작
- STF(상황/생각/감정) 구조가 티 나지 않게 자연스럽게 녹임
- 2~4문장

{{
  "dominant": "감정 영문 키",
  "scores": {{"joy":정수,"excitement":정수,"neutral":정수,"surprise":정수,
              "disgust":정수,"fear":정수,"sadness":정수,"anger":정수}},
  "diary_text": "위 지침에 따라 STF를 1인칭 구어체 일기로 재작성 (2~4문장, STF 구조 노출 금지)",
  "summary": "STF 기록 기반 2문장 이내 감정 요약",
  "empathy": "감정을 구체적으로 인정하는 따뜻한 공감 2~3문장",
  "book_title": "이 감정 상태에 어울리는 한국 소설 또는 에세이 제목",
  "book_author": "저자명"
}}

scores 합계 = 100"""

    message = _client1().messages.create(
        model="claude-opus-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    usage = _usage(message)
    raw   = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    print(f"[LLM단독/Key1] 토큰: 입력={usage['input_tokens']}, 출력={usage['output_tokens']}")
    return json.loads(raw), usage


# ── LLM+NLP 검토 (NLP 결과를 LLM이 검증·보완) ────────────────────────────────
def llm_review_and_generate(
    situation: str, thought: str, feeling: str,
    nlp_dominant: str, nlp_scores: dict,
) -> tuple[dict, dict]:
    """
    STF + NLP 결과를 받아 LLM이 검토하고 감정 요약·공감·도서 추천을 반환.
      - NLP 맞으면: summary/empathy/book 생성 (토큰 절약)
      - NLP 틀리면: 감정 재분류 + summary/empathy/book 생성
    반환: (result_dict, token_usage_dict)
    """
    scores_str = (
        ", ".join(f"{EN_TO_KO[k]}:{v}%" for k, v in nlp_scores.items())
        if nlp_scores
        else ", ".join(f"{EN_TO_KO[k]}:{v}%" for k, v in NLP_SCORE_TEMPLATE[nlp_dominant].items())
    )

    prompt = f"""감정 분석 검토자입니다.

STF: 상황={situation} / 생각={thought} / 감정={feeling}
NLP결과: {EN_TO_KO[nlp_dominant]}({nlp_dominant}), 점수={scores_str}

NLP가 맞으면 nlp_ok:true, 틀리면 nlp_ok:false로 재분류.

[diary_text 작성 지침] 1인칭 구어체, "오늘 ~했다" 형식, 2~4문장, STF 구조 노출 금지.

JSON만 반환:
맞을때: {{"nlp_ok":true,"diary_text":"위 지침대로 작성한 1인칭 구어체 일기 (2~4문장)","summary":"...","empathy":"...","book_title":"...","book_author":"..."}}
틀릴때: {{"nlp_ok":false,"dominant":"반드시 영문키(joy/excitement/neutral/surprise/disgust/fear/sadness/anger 중 하나)","scores":{{"joy":0,...}},"diary_text":"위 지침대로 작성한 1인칭 구어체 일기 (2~4문장)","summary":"...","empathy":"...","book_title":"...","book_author":"..."}}"""
    message = _client2().messages.create(
        model="claude-opus-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    usage = _usage(message)
    raw   = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    print(f"[LLM+NLP/Key2] 토큰: 입력={usage['input_tokens']}, 출력={usage['output_tokens']}")
    return json.loads(raw), usage


# ── 주간 통계용 도서 추천 ────────────────────────────────────────────────────
def get_book_recommendation(dominant: str, filled_records: list) -> dict | None:
    dom_count, score_sums, diary_excerpts = {}, {k: 0.0 for k in EMOTIONS}, []
    for r in filled_records:
        rec = r["record"]
        dom_count[rec["dominant"]] = dom_count.get(rec["dominant"], 0) + 1
        for k in EMOTIONS:
            score_sums[k] += rec["scores"].get(k, 0)
        if rec.get("diary_text"):
            diary_excerpts.append(rec["diary_text"][:60])

    top_emotion = max(dom_count, key=dom_count.get)
    top_ko      = EN_TO_KO.get(top_emotion, top_emotion)
    avg_scores  = {k: round(v / len(filled_records), 1) for k, v in score_sums.items()}

    try:
        msg = _client2().messages.create(
            model="claude-opus-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content":
                f"최근 {len(filled_records)}일간의 감정 데이터입니다.\n"
                f"주요 감정: {top_ko}\n"
                f"평균 감정 점수: {avg_scores}\n"
                f"일기 내용 발췌: {' / '.join(diary_excerpts)}\n\n"
                f"이 사람에게 어울리는 한국 소설 또는 에세이를 1권만 추천해주세요.\n"
                f"형식: 제목|||저자 (다른 텍스트 없이 이 형식만 출력하세요.)"}],
        )
        book_raw    = msg.content[0].text.strip()
        book_parts  = book_raw.split("|||")
        book_title  = book_parts[0].strip()
        book_author = book_parts[1].strip() if len(book_parts) > 1 else ""
        return fetch_book_info(book_title, book_author)
    except Exception as e:
        print(f"[주간 도서 추천] 오류: {e}")
        return None
