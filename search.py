"""
search.py
------------------------------------------------
Web search and YouTube search, used two ways:
1. Explicitly via !search <query> and !youtube <query>
2. Automatically inside !ai -- if a question looks like it needs
   current info (weather, news, scores, prices, "latest", etc.), the
   bot searches first and feeds the results into the AI's context
   before answering, so it isn't relying on stale training data.

Uses the free DuckDuckGo search library (no API key needed) for web
search. YouTube search uses the official YouTube Data API if a key is
provided (more reliable, direct video links); otherwise it falls back
to a DuckDuckGo search restricted to youtube.com.

Install: pip install duckduckgo-search
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    # The package was renamed from duckduckgo_search to ddgs -- try
    # the new name first, fall back to the old one so this keeps
    # working either way depending on what's installed.
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

import requests

# Keywords that suggest a question needs current/real-world info rather
# than something the AI can answer from general knowledge alone.
CURRENT_INFO_KEYWORDS = [
    "weather", "forecast", "temperature",
    "news", "latest", "today", "right now", "currently",
    "score", "result", "who won",
    "price", "cost", "worth",
    "current version", "release date", "when is", "when does",
]

# Keywords that suggest the person wants an actual video/link, not
# just information -- these trigger a YouTube search instead of (or
# alongside) a web search.
YOUTUBE_KEYWORDS = [
    "youtube", "video", "watch", "song", "music video",
    "link to the song", "link to that song", "link to", "clip", "trailer",
]


def needs_current_info(question: str) -> bool:
    """Heuristic check: does this question likely need a web search?"""
    lowered = question.lower()
    return any(keyword in lowered for keyword in CURRENT_INFO_KEYWORDS)


def needs_youtube_search(question: str) -> bool:
    """Heuristic check: does this question likely want a video link?"""
    lowered = question.lower()
    return any(keyword in lowered for keyword in YOUTUBE_KEYWORDS)


def web_search(query: str, max_results: int = 3) -> Optional[str]:
    """
    Searches the web and returns a short plain-text summary of the top
    results, or None if search is unavailable/fails.
    """
    if not DDGS:
        logger.warning("[SEARCH] duckduckgo-search not installed, skipping web search.")
        return None

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return None

        lines = []
        for r in results:
            title = r.get("title", "")
            snippet = r.get("body", "")
            lines.append(f"{title}: {snippet}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[SEARCH] Web search failed: {e}")
        return None


# Common filler phrases that, left in, pollute a search query with
# noise unrelated to the actual thing being searched for -- especially
# damaging for the site-restricted fallback search, which is a literal
# text match, not a semantic one.
_YOUTUBE_FILLER_PATTERNS = [
    r"\bcan you\b", r"\bcould you\b", r"\bplease\b",
    r"\bgive me\b", r"\bfind me\b", r"\bsend me\b", r"\bshow me\b",
    r"\bthe link to\b", r"\ba link to\b", r"\blink to\b", r"\blink for\b",
    r"\bfrom youtube\b", r"\bon youtube\b", r"\byoutube\b",
    r"\bvideo of\b", r"\bvideo for\b", r"\bthe video\b",
    r"\bsong called\b", r"\bthe song\b",
]


def _clean_youtube_query(question: str) -> str:
    """
    Strips common request-phrasing filler from a natural-language
    question, leaving (ideally) just the actual subject -- e.g. "give
    me the link to heaven or las vegas from youtube, please" becomes
    "heaven or las vegas". Not perfect, but removes the noise that
    most damages a site-restricted search.
    """
    cleaned = question.lower()
    for pattern in _YOUTUBE_FILLER_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[,.!?]+", " ", cleaned)  # drop stray punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or question  # fall back to the original if we stripped everything


def youtube_search(query: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Searches YouTube and returns a title + direct link to the first
    result, or None if search fails.
    """
    query = _clean_youtube_query(query)
    if api_key:
        return _youtube_search_official(query, api_key)
    return _youtube_search_fallback(query)


def _youtube_search_official(query: str, api_key: str) -> Optional[str]:
    """Uses the official YouTube Data API for a reliable, direct result."""
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 1,
                "key": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None

        video_id = items[0]["id"]["videoId"]
        title = items[0]["snippet"]["title"]
        return f"{title} - https://www.youtube.com/watch?v={video_id}"
    except requests.RequestException as e:
        logger.error(f"[SEARCH] YouTube API search failed: {e}")
        return None
    except (KeyError, IndexError) as e:
        logger.error(f"[SEARCH] Unexpected YouTube API response shape: {e}")
        return None


def _youtube_search_fallback(query: str) -> Optional[str]:
    """
    No API key configured -- searches the web restricted to
    youtube.com and returns the first video link found. Less reliable
    than the official API, but requires no setup.
    """
    if not DDGS:
        return None

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"site:youtube.com/watch {query}", max_results=3))

        for r in results:
            url = r.get("href", "")
            if "youtube.com/watch" in url:
                title = r.get("title", "")
                return f"{title} - {url}"

        return None
    except Exception as e:
        logger.error(f"[SEARCH] YouTube fallback search failed: {e}")
        return None
