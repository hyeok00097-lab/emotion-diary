# Emonote — AI 기반 감정일기 서비스

STF(Situation·Thought·Feeling) 프레임워크로 지금 있었던 일을 기록하면,  
KoELECTRA + Claude가 감정을 분석하고 공감 메시지·음악·명상 가이드를 추천해주는 웹 앱입니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **대화형 일기** | AI와 채팅하며 자연스럽게 STF 파악 |
| **직접 입력** | 상황·생각·감정을 직접 작성 |
| **감정 분석** | KoELECTRA(로컬) + Claude 검토로 8가지 감정 분류 |
| **감정 달력** | 날짜별 감정 이미지로 시각화 |
| **주간 통계** | 7일 감정 흐름 바 차트 + 도서 추천 |
| **음악 추천** | Spotify API로 감정 맞춤 트랙 인앱 재생 |
| **명상 가이드** | 감정별 5분 명상 스크립트 + 배경음악 타이머 |

---

## 설치 방법

### 1단계 — Python 설치

Python 공식 사이트에서 **3.10 이상** 버전을 다운로드해 설치합니다.

> https://www.python.org/downloads/

설치 시 **"Add Python to PATH"** 체크박스를 반드시 체크하세요.

설치 후 명령 프롬프트(cmd)를 열고 확인합니다.

```
python --version
```

`Python 3.x.x` 가 출력되면 정상입니다.

---

### 2단계 — pip 확인 및 업그레이드

pip은 Python 패키지 설치 도구입니다. 보통 Python과 함께 설치되지만, 없거나 오래된 버전일 수 있습니다.

```
python -m pip --version
```

pip이 없다는 오류가 나오면 아래 명령으로 설치합니다.

```
python -m ensurepip --upgrade
```

pip을 최신 버전으로 업그레이드합니다.

```
python -m pip install --upgrade pip
```

---

### 3단계 — 프로젝트 폴더로 이동

명령 프롬프트에서 Emonote 폴더로 이동합니다.  
아래는 예시 경로이며, 실제 경로에 맞게 수정하세요.

```
cd C:\Users\사용자명\Desktop\emotion_diary
```

---

### 4단계 — 패키지 설치

PyTorch(CPU 버전)와 나머지 패키지를 한 번에 설치합니다.  
**처음 설치 시 PyTorch 용량이 크기 때문에 수 분이 걸릴 수 있습니다.**

```
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
```

설치되는 주요 패키지 목록입니다.

| 패키지 | 용도 |
|--------|------|
| `torch` | KoELECTRA 로컬 추론 (CPU 버전) |
| `transformers` | KoELECTRA 모델 로드 |
| `flask` | 웹 서버 |
| `anthropic` | Claude API 호출 |
| `spotipy` | Spotify API |
| `scikit-learn` | 감정 벡터 유사도 계산 |
| `requests` | Google Books API 호출 |
| `python-dotenv` | .env 파일 로드 |

---

### 5단계 — 환경변수(.env) 설정

프로젝트 폴더에 있는 `.env.example` 파일을 복사해 `.env` 파일을 만듭니다.

**Windows 명령 프롬프트:**
```
copy .env.example .env
```

`.env` 파일을 메모장이나 텍스트 편집기로 열어 API 키를 입력합니다.

```
ANTHROPIC_API_KEY_1=여기에_키_입력
ANTHROPIC_API_KEY_2=여기에_키_입력
SPOTIFY_CLIENT_ID=여기에_키_입력
SPOTIFY_CLIENT_SECRET=여기에_키_입력
GOOGLE_BOOKS_API_KEY=여기에_키_입력
```

#### API 키 발급처

| 변수명 | 필수 | 발급 주소 |
|--------|:----:|-----------|
| `ANTHROPIC_API_KEY_1` | ✅ | https://console.anthropic.com |
| `ANTHROPIC_API_KEY_2` | ✅ | https://console.anthropic.com |
| `SPOTIFY_CLIENT_ID` | ⬜ | https://developer.spotify.com/dashboard |
| `SPOTIFY_CLIENT_SECRET` | ⬜ | https://developer.spotify.com/dashboard |
| `GOOGLE_BOOKS_API_KEY` | ⬜ | https://console.cloud.google.com |

> Anthropic API 키 2개가 없으면 감정 분석 및 대화 기능이 동작하지 않습니다.  
> Spotify·Google Books 키는 선택 사항이며, 없으면 해당 카드만 비어있습니다.

---

### 6단계 — 실행

**Windows에서 더블클릭으로 실행:**

`run.bat` 파일을 더블클릭합니다.  
서버가 준비되면 브라우저가 자동으로 열립니다.

**명령 프롬프트에서 직접 실행:**

```
python app.py
```

실행 후 브라우저에서 아래 주소로 접속합니다.

```
http://localhost:5000
```

서버를 종료할 때는 `Ctrl+C` 를 누릅니다.

---

### 처음 실행 시 주의사항

최초 실행 시 KoELECTRA 모델 파일을 자동으로 다운로드합니다.  
인터넷이 연결되어 있어야 하며, 다운로드에 수 분이 소요될 수 있습니다.  
다운로드가 완료되면 이후부터는 즉시 실행됩니다.

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
│   ├── emotions/           # 감정별 이미지 8종
│   └── Meditation_Music/   # 로컬 배경음악 5종 (.mp3)
│
├── .env                    # API 키 (직접 작성, git 제외)
├── .env.example            # 키 구조 예시
├── requirements.txt        # Python 패키지 목록
├── run.bat                 # Windows 더블클릭 실행 파일
└── emonote.db              # SQLite DB (자동 생성)
```

---

## 기술 스택

- **백엔드**: Flask, SQLite, Python 3.10+
- **AI 분석**: KoELECTRA (`LimYeri/HowRU-KoELECTRA-Emotion-Classifier`) + Claude (`claude-opus-4-5`)
- **대화 모드**: Claude (`claude-sonnet-4-5`)
- **외부 API**: Anthropic, Spotify Web API, Google Books API
- **프론트엔드**: Vanilla JS, CSS (프레임워크 없음)

---

## 문제 해결

**`python` 명령이 없다고 나올 때**

Python 설치 시 PATH 설정이 안 된 경우입니다.  
Python을 재설치하면서 "Add Python to PATH"를 체크하거나,  
`py` 명령으로 대신 실행해보세요.

```
py --version
py app.py
```

**패키지 설치 중 오류가 날 때**

pip을 먼저 업그레이드한 후 다시 시도하세요.

```
python -m pip install --upgrade pip
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
```

**서버는 켜졌는데 브라우저에서 접속이 안 될 때**

브라우저 주소창에 직접 입력하세요.

```
http://127.0.0.1:5000
```

**KoELECTRA 모델 다운로드가 너무 느릴 때**

최초 1회만 다운로드가 필요합니다. 완료 후에는 로컬에 캐시됩니다.  
다운로드 경로: `C:\Users\사용자명\.cache\huggingface\`
