"""환경변수 로드 및 API 키 관리 — .env 파일 읽기/쓰기와 외부 서비스 키 노출."""
import os
from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values

ENV_FILE = Path(__file__).parent / ".env"

# 앱 시작 시 초기 로드
load_dotenv(ENV_FILE)


def _read_env() -> dict:
    """파일에서 직접 읽어 항상 최신 값을 반환 (os.environ 캐시 우회)."""
    return dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}


def save_api_keys(key1: str, key2: str) -> None:
    """설정 UI 저장 시 .env 파일에 기록하고 os.environ도 즉시 갱신."""
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    set_key(str(ENV_FILE), "ANTHROPIC_API_KEY_1", key1.strip())
    set_key(str(ENV_FILE), "ANTHROPIC_API_KEY_2", key2.strip())
    os.environ["ANTHROPIC_API_KEY_1"] = key1.strip()
    os.environ["ANTHROPIC_API_KEY_2"] = key2.strip()


def get_api_key_1() -> str:
    """LLM 단독 분석용 키 (.env ANTHROPIC_API_KEY_1)."""
    return _read_env().get("ANTHROPIC_API_KEY_1") or ""


def get_api_key_2() -> str:
    """LLM+NLP 검토용 키 (.env ANTHROPIC_API_KEY_2)."""
    return _read_env().get("ANTHROPIC_API_KEY_2") or ""


def get_keys_status() -> dict:
    """현재 키 설정 상태를 마스킹해서 반환 (설정 UI용)."""
    def mask(k: str) -> str:
        if not k:
            return ""
        return k[:10] + "·····" + k[-4:] if len(k) > 14 else k[:4] + "·····"

    k1, k2 = get_api_key_1(), get_api_key_2()
    return {
        "key1_masked": mask(k1),
        "key2_masked": mask(k2),
        "key1_set":    bool(k1),
        "key2_set":    bool(k2),
    }


# ── 나머지 외부 API 키 (.env 전용, 앱 시작 시 1회 로드) ──────────────────────
GOOGLE_BOOKS_API_KEY  = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
SPOTIFY_CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
PIXABAY_API_KEY       = os.environ.get("PIXABAY_API_KEY", "")

DB_PATH = "emonote.db"
