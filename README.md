# Emonote — AI 기반 감정일기 서비스

STF(Situation·Thought·Feeling) 프레임워크로 하루를 기록하면,
KoELECTRA + Claude가 감정을 분석하고 공감 메시지·음악·명상 가이드를 추천해주는 웹 앱입니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **대화형 일기** | AI와 채팅하며 자연스럽게 STF 파악 |
| **직접 입력** | 상황·생각·감정을 직접 작성 |
| **감정 분석** | KoELECTRA(로컬) + Claude 검토로 8가지 감정 분류 |
| **감정 달력** | 날짜별 감정 기록 시각화 |
| **주간 통계** | 7일 감정 흐름 바 차트 + 도서 추천 |
| **음악 추천** | Spotify API로 감정 맞춤 트랙 추천 |
| **명상 가이드** | 감정별 5분 명상 스크립트 + 배경음악 타이머 |

---

## 설치 방법

```bash
# 1. 저장소 클론
git clone https://github.com/yourname/emotion_diary.git
cd emotion_diary

# 2. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 각 키 값을 입력하세요

# 3. 패키지 설치 (CPU PyTorch 포함)
pip install -r requirements.txt

# 4. 서버 실행
python app.py
# 또는 Windows에서 run.bat 더블클릭
```

브라우저에서 http://localhost:5000 접속

---

## 환경변수 설명

`.env` 파일에 아래 키를 입력하세요.

| 변수명 | 필수 | 발급처 | 용도 |
|--------|------|--------|------|
| `ANTHROPIC_API_KEY_1` | ✅ | [console.anthropic.com](https://console.anthropic.com) | LLM 단독 분석 (유사도 비교용) |
| `ANTHROPIC_API_KEY_2` | ✅ | [console.anthropic.com](https://console.anthropic.com) | KoELECTRA 검토 + 대화형 모드 |
| `SPOTIFY_CLIENT_ID` | ⬜ | [developer.spotify.com](https://developer.spotify.com/dashboard) | 음악 추천 (없으면 음악 카드 비어있음) |
| `SPOTIFY_CLIENT_SECRET` | ⬜ | [developer.spotify.com](https://developer.spotify.com/dashboard) | 음악 추천 |
| `GOOGLE_BOOKS_API_KEY` | ⬜ | [console.cloud.google.com](https://console.cloud.google.com) | 도서 표지·메타데이터 조회 |

> Anthropic API 키 2개가 없으면 분석이 동작하지 않습니다.  
> 나머지 키는 선택 사항이며, 없으면 해당 기능만 비활성화됩니다.

---

## 폴더 구조

```
emotion_diary/
├── app.py                  # Flask 서버 + API 엔드포인트
├── config.py               # 환경변수 로드 및 API 키 관리
├── database.py             # SQLite CRUD + 마이그레이션
├── llm.py                  # Claude API 호출 (분석·대화·도서추천)
├── nlp.py                  # KoELECTRA 감정 분류
├── emotions.py             # 감정 레이블·매핑·검색 쿼리 정의
├── meditation.py           # 감정별 명상 가이드 8종
├── spotify_api.py          # Spotify 트랙 검색
├── books_api.py            # Google Books API 도서 정보 조회
│
├── templates/
│   └── index.html          # 단일 페이지 UI
│
├── static/
│   ├── css/style.css       # 전체 스타일
│   ├── js/app.js           # 프론트엔드 로직 (탭·슬라이더·채팅·달력 등)
│   └── Meditation_Music/   # 로컬 배경음악 5종 (.mp3)
│
├── .env                    # API 키 (git 제외)
├── .env.example            # 키 구조 예시
├── requirements.txt        # Python 패키지 목록
├── run.bat                 # Windows 더블클릭 실행 파일
└── emonote.db              # SQLite DB (자동 생성)
```

---

## 기술 스택

- **백엔드**: Flask, SQLite, Python 3.10+
- **AI 분석**: KoELECTRA (`LimYeri/HowRU-KoELECTRA-Emotion-Classifier`) + Claude (`claude-opus-4-5`)
- **외부 API**: Anthropic, Spotify Web API, Google Books API
- **프론트엔드**: Vanilla JS, CSS (프레임워크 없음)
