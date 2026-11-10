"""Recent news lookup using Tavily's search API.

This module only performs retrieval. The orchestrator must obtain user confirmation
before invoking search_news.
"""
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool


def _published_at(value: object) -> datetime | None:
    """Parse Tavily news dates in ISO, date-only or RFC 2822 format."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        date = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            date = parsedate_to_datetime(value.strip())
        except (ValueError, TypeError, IndexError, OverflowError):
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc)


@tool
async def search_news(query: str, days_back: int = 7, max_results: int = 5, country: str = "IT") -> dict:
    """Search for recent factual news relevant to a homily, after explicit user confirmation.

    Args:
        query: Search terms or pastoral theme.
        days_back: Number of recent days to search (1-30).
        max_results: Maximum articles returned (1-10).
        country: Country context, e.g. IT (Italy). Used as a search hint.
    """
    query = query.strip()
    if not query or len(query) > 300:
        return {"error": "La ricerca deve contenere da 1 a 300 caratteri.", "articles": []}
    if not 1 <= days_back <= 30 or not 1 <= max_results <= 10:
        return {"error": "days_back deve essere 1-30 e max_results 1-10.", "articles": []}

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"error": "Ricerca notizie non configurata: manca TAVILY_API_KEY.", "articles": []}

    country_hint = "Italia" if country.upper() == "IT" else country[:30]
    payload = {
        "api_key": api_key,
        "query": f"{query} {country_hint} notizie cronaca",
        "topic": "news",
        "days": days_back,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {"error": f"Ricerca notizie non disponibile: {type(exc).__name__}", "articles": []}

    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return {"error": "Risposta non valida dal servizio di notizie.", "articles": []}

    articles = []
    seen = set()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)
    for item in data["results"]:
        # One malformed record must not abort valid siblings.
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str):
            continue
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        if parsed.scheme != "https" or not parsed.hostname or url in seen:
            continue
        date = _published_at(item.get("published_date") or item.get("published_at"))
        if date is None or not cutoff <= date <= now + timedelta(days=1):
            continue
        seen.add(url)
        articles.append({
            "title": str(item.get("title") or "")[:300],
            "source": parsed.netloc,
            "published_at": date.date().isoformat(),
            "url": url,
            "summary": str(item.get("content") or "")[:800],
        })
    return {"query": query, "articles": articles[:max_results], "note": "Verificare le fonti originali prima di citare le notizie nell'omelia."}
