import requests
from config import GOOGLE_BOOKS_API_KEY


def fetch_book_info(book_title: str, book_author: str) -> dict:
    """Google Books API로 도서 상세 정보 조회."""
    try:
        gb    = requests.get("https://www.googleapis.com/books/v1/volumes", params={
            "q": f"{book_title} {book_author}", "langRestrict": "ko",
            "maxResults": 1, "key": GOOGLE_BOOKS_API_KEY,
        }).json()
        items = gb.get("items", [])
        if items:
            vol   = items[0]["volumeInfo"]
            thumb = vol.get("imageLinks", {}).get("thumbnail", "").replace("http://", "https://")
            desc  = vol.get("description", "")
            return {
                "title":       vol.get("title", book_title),
                "author":      ", ".join(vol.get("authors", [book_author])),
                "publisher":   vol.get("publisher", ""),
                "published":   vol.get("publishedDate", "")[:4],
                "pages":       vol.get("pageCount", ""),
                "description": desc[:120] + "..." if len(desc) > 120 else desc,
                "thumbnail":   thumb,
            }
    except Exception as e:
        print(f"[Google Books] API 오류: {e}")
    return {"title": book_title, "author": book_author, "publisher": "",
            "published": "", "pages": "", "description": "", "thumbnail": ""}
