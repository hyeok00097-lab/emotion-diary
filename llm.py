"""Claude API 호출 — LLM 단독 분석·NLP 검토·대화형 STF 추출·도서 추천."""
import json
import time
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


# ── JSON 파싱 재시도 헬퍼 ─────────────────────────────────────────────────────
def _call_with_retry(
    client: anthropic.Anthropic,
    prompt: str,
    max_tokens: int,
    label: str,
) -> tuple[dict, dict]:
    """
    Claude API 호출 후 JSON 파싱을 최대 3회 시도 (최초 1회 + 재시도 2회).

    재시도 전략:
      - 실패한 Claude 응답을 assistant 턴으로 넣어 멀티턴 구성
      - "JSON만 출력" 강조 메시지를 user 턴에 추가해 재요청
      - 3회 모두 실패하면 ValueError 발생 → app.py의 except로 전파

    Args:
        client:     사용할 Anthropic 클라이언트 (Key1 또는 Key2)
        prompt:     최초 요청 프롬프트
        max_tokens: 최대 출력 토큰 수
        label:      로그 식별자 (예: "LLM단독/Key1")

    Returns:
        (파싱된 dict, 토큰 사용량 dict) — 마지막 성공 시도 기준
    """
    MAX_ATTEMPTS = 3
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(MAX_ATTEMPTS):
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=max_tokens,
            messages=messages,
        )
        usage = _usage(message)
        # 마크다운 코드블록 제거 후 양쪽 공백 정리
        raw = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        print(f"[{label}] 시도 {attempt + 1}/{MAX_ATTEMPTS} | "
              f"토큰: 입력={usage['input_tokens']}, 출력={usage['output_tokens']}")

        try:
            return json.loads(raw), usage
        except json.JSONDecodeError as e:
            print(f"[{label}] JSON 파싱 실패 (시도 {attempt + 1}/{MAX_ATTEMPTS}): {e}")
            print(f"[{label}] 응답 앞 200자: {raw[:200]}")

            if attempt < MAX_ATTEMPTS - 1:
                # 멀티턴: 실패한 응답을 assistant 턴으로 추가하고,
                # 순수 JSON만 재출력하도록 user 턴에 강조 메시지 삽입
                messages.append({"role": "assistant", "content": message.content[0].text})
                messages.append({
                    "role": "user",
                    "content": (
                        "응답에 JSON 외 텍스트가 포함되어 있거나 JSON이 완성되지 않았습니다. "
                        "반드시 유효한 JSON만, 설명·마크다운·추가 문장 없이 바로 출력하세요. "
                        "첫 글자는 { 이어야 합니다."
                    ),
                })

    raise ValueError(f"[{label}] JSON 파싱 {MAX_ATTEMPTS}회 모두 실패")


# ── LLM 단독 분석 (NLP 없이 Claude가 전부 처리) ──────────────────────────────
def llm_only_analyze(
    situation: str, thought: str, feeling: str,
) -> tuple[dict, dict]:
    """
    KoELECTRA 없이 LLM이 감정 분류부터 추천까지 전부 수행.
    토큰 사용량 비교 전용 — 결과는 DB에 저장하지 않음.

    Returns:
        (result_dict, token_usage_dict)
    """
    prompt = f"""당신은 감정 일기 분석 전문가입니다.

[STF 감정 기록]
상황(Situation): {situation}
생각(Thought):   {thought}
감정(Feeling):   {feeling}

위 STF 기록을 분석하여 아래 8가지 감정 중 가장 지배적인 하나를 선택하고,
각 감정의 비율(합계=100), 공감, 도서 추천을 JSON으로만 반환하세요.
다른 텍스트 없이 JSON만 출력하세요. 첫 글자는 {{ 이어야 합니다.

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
  "empathy": "감정을 구체적으로 인정하는 따뜻한 공감 2~3문장",
  "book_title": "이 감정 상태에 어울리는 한국 소설 또는 에세이 제목",
  "book_author": "저자명"
}}

scores 합계 = 100"""

    return _call_with_retry(_client1(), prompt, max_tokens=1000, label="LLM단독/Key1")


# ── LLM+NLP 검토 (NLP 결과를 LLM이 검증·보완) ────────────────────────────────
def llm_review_and_generate(
    situation: str, thought: str, feeling: str,
    nlp_dominant: str, nlp_scores: dict,
) -> tuple[dict, dict]:
    """
    STF + NLP 결과를 받아 LLM이 검토하고 공감·도서 추천을 반환.
      - NLP 맞으면: nlp_ok=true, empathy/diary_text/book 생성 (토큰 절약)
      - NLP 틀리면: nlp_ok=false, 감정 재분류 + empathy/diary_text/book 생성

    Returns:
        (result_dict, token_usage_dict)
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
다른 텍스트 없이 JSON만 출력하세요. 첫 글자는 {{ 이어야 합니다.

[diary_text 작성 지침] 1인칭 구어체, "오늘 ~했다" 형식, 2~4문장, STF 구조 노출 금지.

맞을때: {{"nlp_ok":true,"diary_text":"위 지침대로 작성한 1인칭 구어체 일기 (2~4문장)","empathy":"...","book_title":"...","book_author":"..."}}
틀릴때: {{"nlp_ok":false,"dominant":"반드시 영문키(joy/excitement/neutral/surprise/disgust/fear/sadness/anger 중 하나)","scores":{{"joy":0,...}},"diary_text":"위 지침대로 작성한 1인칭 구어체 일기 (2~4문장)","empathy":"...","book_title":"...","book_author":"..."}}"""

    return _call_with_retry(_client2(), prompt, max_tokens=1000, label="LLM+NLP/Key2")


# ── 대화형 모드: 사용자와 대화하며 STF 추출 ──────────────────────────────────
def chat_with_user(messages: list) -> dict:
    """
    대화 히스토리를 받아 다음 AI 응답 반환.
    STF가 파악되면 done=false + ready=true로 마무리 멘트와 STF를 함께 반환.
    프론트엔드가 "기록하기" 버튼을 보여주고, 사용자가 확인 후 분석 파이프라인을 시작함.

    Args:
        messages: [{"role": "user"|"assistant", "content": "..."}, ...]
                  첫 번째 메시지는 반드시 role="user"

    Returns:
        대화 중:  {"done": false, "message": "다음 질문"}
        STF 완료: {"done": false, "ready": true, "message": "마무리 멘트",
                   "situation": "...", "thought": "...", "feeling": "..."}
    """
    if not messages:
        return {"done": False, "message": "안녕하세요! 오늘 하루 어떠셨나요? 😊"}

    system_prompt = (
        "당신은 감정일기 작성을 돕는 친근한 AI입니다.\n"
        "사용자와 자연스러운 대화를 통해 오늘 있었던\n"
        "상황(Situation), 생각(Thought), 감정(Feeling)을 파악하세요.\n\n"
        "[대화 원칙]\n"
        "- 친구한테 말하듯 편하고 따뜻하게 대화하세요\n"
        "- 질문은 한 번에 하나씩만 하세요\n"
        "- 절대 처음부터 바로 질문하지 마세요\n"
        "- 사용자의 말에 먼저 공감하고 자연스럽게 이어가세요\n\n"
        "[감정 표현 처리 원칙]\n"
        "- '나쁘지않았어', '그냥', '괜찮았어', 'soso', '모르겠어',\n"
        "  '별로', '그저그래' 같은 중립적/애매한 표현은\n"
        "  그 자체로 하나의 감정 상태로 인정하고 수용하세요\n"
        "- 절대 더 구체적인 감정을 캐묻지 마세요\n"
        "- 대신 '그렇구나~', 'ㅋㅋ 그런 날도 있지' 처럼\n"
        "  자연스럽게 공감하고 넘어가세요\n"
        "- STF가 완벽하지 않아도 대화가 자연스럽게\n"
        "  마무리되면 ready: true로 처리하세요\n\n"
        "[마무리 기준]\n"
        "- 오늘 있었던 일(Situation)이 파악되면\n"
        "- 생각이나 감정이 애매해도 사용자가 더 말하기\n"
        "  싫어하는 느낌이면 자연스럽게 마무리하세요\n\n"
        "[마무리 멘트 작성 요령]\n"
        "- 오늘 대화를 짧게 공감으로 마무리하세요\n"
        "- 반드시 '더 하고 싶은 말 있어? 없으면 아래 버튼 눌러서 기록해줘!' 를 포함하세요\n"
        "- 예시: '오늘 있었던 일 잘 들었어 😊 더 하고 싶은 말 있어? 없으면 아래 버튼 눌러서 기록해줘!'\n\n"
        "반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):\n"
        "STF 파악 중: {\"done\": false, \"message\": \"사용자에게 보낼 자연스러운 대화 메시지\"}\n"
        "STF 파악 완료: {\"done\": false, \"ready\": true, \"message\": \"마무리 멘트\", "
        "\"situation\": \"상황 요약\", \"thought\": \"생각 요약\", \"feeling\": \"감정 요약\"}\n"
        "첫 글자는 { 이어야 합니다."
    )

    # 529 과부하 및 JSON 파싱 실패 모두 최대 2회 재시도
    MAX_RETRIES = 2
    for attempt in range(MAX_RETRIES + 1):
        try:
            message = _client2().messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1000,
                system=system_prompt,
                messages=messages,
            )
            raw = (message.content[0].text.strip()
                   .replace("```json", "").replace("```", "").strip())
            result = json.loads(raw)
            print(f"[대화형] done={result.get('done')} | {raw[:80]}")
            return result

        except json.JSONDecodeError as e:
            # JSON 파싱 실패: 재시도 가능하면 재시도, 아니면 안내 메시지 반환
            print(f"[대화형] JSON 파싱 실패 (시도 {attempt + 1}/{MAX_RETRIES + 1}): {e}")
            if attempt < MAX_RETRIES:
                continue
            return {"done": False,
                    "message": "죄송해요, 잠깐 문제가 생겼어요. 다시 말씀해주실 수 있을까요?"}

        except anthropic.APIStatusError as e:
            # 529 과부하: 1초 대기 후 재시도
            if e.status_code == 529 and attempt < MAX_RETRIES:
                print(f"[대화형] 529 과부하 (시도 {attempt + 1}/{MAX_RETRIES + 1}), 1초 후 재시도")
                time.sleep(1)
                continue
            print(f"[대화형] API 오류 (status={e.status_code}): {e}")
            raise

        except Exception as e:
            print(f"[대화형] 오류: {e}")
            raise


def extract_stf_from_chat(messages: list) -> dict:
    """
    대화 히스토리에서 STF를 명시적으로 추출 (기존 분석 파이프라인 연결용).

    Args:
        messages: chat_with_user에 전달한 것과 동일한 대화 히스토리

    Returns:
        {"situation": "...", "thought": "...", "feeling": "..."}
    """
    conversation = "\n".join(
        f"{'사용자' if m['role'] == 'user' else 'AI'}: {m['content']}"
        for m in messages
    )

    prompt = (
        f"다음 감정일기 대화에서 STF를 추출해주세요.\n\n"
        f"대화:\n{conversation}\n\n"
        "다른 텍스트 없이 JSON만 반환하세요. 첫 글자는 { 이어야 합니다.\n"
        "{\"situation\": \"오늘 있었던 상황 요약\", "
        "\"thought\": \"그때 든 생각 요약\", "
        "\"feeling\": \"느낀 감정 요약\"}"
    )

    result, _ = _call_with_retry(_client2(), prompt, max_tokens=300, label="STF추출")
    return result


# ── 하루 여러 감정 기록 → 일기 자동 생성 ─────────────────────────────────────
def generate_daily_diary(records: list) -> str:
    """
    하루의 감정 기록 목록으로 1인칭 일기체 텍스트를 생성.

    Args:
        records: get_records_by_date() 반환값 — 각 항목은
                 {situation, thought, feeling, diary_text, dominant, scores, empathy, recorded_at}

    Returns:
        완성된 일기 텍스트 (3~5문장 구어체)
    """
    entries = []
    for i, r in enumerate(records, 1):
        time_str = r.get("recorded_at", "")[:16]   # "YYYY-MM-DD HH:MM"
        parts = []
        if r.get("situation"):
            parts.append(f"상황: {r['situation']}")
        if r.get("thought"):
            parts.append(f"생각: {r['thought']}")
        if r.get("feeling"):
            parts.append(f"감정: {r['feeling']}")
        if r.get("diary_text"):
            parts.append(f"기록: {r['diary_text']}")
        entries.append(f"[기록 {i} | {time_str}]\n" + "\n".join(parts))

    prompt = (
        "다음은 오늘 하루 동안 기록된 감정 기록들입니다.\n"
        "이를 바탕으로 하루를 돌아보는 자연스러운 1인칭 일기체 3~5문장으로 작성해주세요.\n"
        "시간 순서대로 자연스럽게 연결하고 구어체로 작성하세요.\n"
        "일기 텍스트만 출력하고 다른 설명은 쓰지 마세요.\n\n"
        + "\n\n".join(entries)
    )

    try:
        message = _client2().messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        diary = message.content[0].text.strip()
        print(f"[일기 생성] {len(records)}개 기록 → {len(diary)}자")
        return diary
    except Exception as e:
        print(f"[일기 생성] 오류: {e}")
        # 오류 시 마지막 diary_text 반환
        for r in reversed(records):
            if r.get("diary_text"):
                return r["diary_text"]
        return ""


# ── 주간 통계용 도서 추천 ────────────────────────────────────────────────────
def get_book_recommendation(diaries: list) -> dict | None:
    """
    최근 7일 daily_diary 기록을 바탕으로 도서 1권 추천.

    Args:
        diaries: get_weekly_diaries() 반환값
                 [{"date", "diary_text", "dominant", "scores"}, ...]

    Returns:
        fetch_book_info() 반환 dict 또는 None
    """
    if not diaries:
        return None

    # 날짜별 일기 요약 (날짜 + 주요 감정 + 일기 앞 80자)
    diary_lines = []
    for d in diaries:
        dom_ko = EN_TO_KO.get(d["dominant"], d["dominant"])
        excerpt = d["diary_text"][:80].replace("\n", " ") if d["diary_text"] else "(내용 없음)"
        diary_lines.append(f"[{d['date']} · {dom_ko}] {excerpt}")

    prompt = (
        "다음은 최근 7일간의 감정 일기입니다.\n"
        "날짜별 주요 감정과 일기 내용을 종합하여\n"
        "이 사람에게 가장 어울리는 한국 소설 또는 에세이 1권을 추천해주세요.\n"
        "형식: 제목|||저자 (다른 텍스트 없이 이 형식만 출력하세요.)\n\n"
        + "\n".join(diary_lines)
    )

    try:
        msg = _client2().messages.create(
            model="claude-opus-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        book_raw    = msg.content[0].text.strip()
        book_parts  = book_raw.split("|||")
        book_title  = book_parts[0].strip()
        book_author = book_parts[1].strip() if len(book_parts) > 1 else ""
        print(f"[주간 도서 추천] {book_title} — {book_author}")
        return fetch_book_info(book_title, book_author)
    except Exception as e:
        print(f"[주간 도서 추천] 오류: {e}")
        return None
