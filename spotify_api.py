import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from emotions import EMOTION_SEARCH_QUERIES

spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
))


def get_playlist(dominant: str) -> dict:
    """Spotify Search API로 감정에 맞는 트랙 1개 추천."""
    queries = EMOTION_SEARCH_QUERIES.get(dominant, EMOTION_SEARCH_QUERIES["neutral"])
    try:
        for query in queries:
            results = spotify.search(q=query, type="track", limit=10, market="KR")
            items   = results["tracks"]["items"]
            if items:
                t = random.choice(items)
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
        print(f"[Spotify] Search API 오류: {e}")
        return {"tracks": [], "error": str(e)}
