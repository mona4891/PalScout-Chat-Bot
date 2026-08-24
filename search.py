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


def needs_current_info(question: str) -> bool:
    """Heuristic check: does this question likely need a web search?"""
    lowered = question.lower()
    return any(keyword in lowered for keyword in CURRENT_INFO_KEYWORDS)


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


def youtube_search(query: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Searches YouTube and returns a title + direct link to the first
    result, or None if search fails.
    """
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
