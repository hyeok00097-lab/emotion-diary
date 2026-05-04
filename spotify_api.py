import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from emotions import EMOTION_SEARCH_QUERIES

# ── 모듈 레벨 클라이언트 제거 ─────────────────────────────────────────────────
# 기존: spotify = spotipy.Spotify(...) 를 모듈 최상단에 두면
#       임포트 시점에 Spotify 인증 서버로 HTTP 요청 발생
#       → 키 없음·네트워크 오류 시 서버 시작 자체가 실패
# 변경: get_playlist() 호출 시마다 클라이언트를 생성해 문제를 함수 내부로 격리


def get_playlist(dominant: str) -> dict:
    """
    Spotify Search API로 감정에 맞는 트랙 1개 추천.

    클라이언트를 매 호출 시 생성하므로 키 미설정·네트워크 오류가
    서버 시작 실패로 이어지지 않고 빈 결과로 안전하게 처리됨.

    Args:
        dominant: 감정 영문 키 (joy / sadness / anger 등)

    Returns:
        {"tracks": [{"title":..., "artist":..., "url":...}], "error": None}
        오류 시: {"tracks": [], "error": "오류 메시지"}
    """
    # 키가 비어있으면 API 호출 없이 즉시 빈 결과 반환
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("[Spotify] API 키가 설정되지 않아 음악 추천을 건너뜁니다.")
        return {"tracks": [], "error": "Spotify API 키 없음"}

    try:
        # 함수 내부에서 클라이언트 생성 — 오류는 아래 except에서 처리
        client = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        ))

        queries = EMOTION_SEARCH_QUERIES.get(dominant, EMOTION_SEARCH_QUERIES["neutral"])
        for query in queries:
            results = client.search(q=query, type="track", limit=10, market="KR")
            items   = results["tracks"]["items"]
            if items:
                t     = random.choice(items)
                track = {
                    "title":    t["name"],
                    "artist":   t["artists"][0]["name"],
                    "track_id": t["id"],
                    "url":      t["external_urls"]["spotify"],
                }
                print(f"[Spotify] 추천곡: {track['title']} - {track['artist']} ({dominant})")
                return {"tracks": [track], "error": None}

        return {"tracks": [], "error": None}

    except Exception as e:
        print(f"[Spotify] 오류: {e}")
        return {"tracks": [], "error": str(e)}
