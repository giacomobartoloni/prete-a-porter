"""Recent news lookup using Tavily's search API.

This module only performs retrieval. The orchestrator must obtain user confirmation
before invoking search_news.
"""
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool


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

    articles = []
    seen = set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    for item in data.get("results", []):
        url = item.get("url", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc or url in seen:
            continue
        published = item.get("published_date") or item.get("published_at")
        if not published:
            continue  # Do not present undated stories as recent news.
        try:
            date = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            if date < cutoff or date > datetime.now(timezone.utc) + timedelta(days=1):
                continue
        except (ValueError, TypeError):
            continue
        seen.add(url)
        articles.append({
            "title": str(item.get("title", ""))[:300],
            "source": parsed.netloc,
            "published_at": date.date().isoformat(),
            "url": url,
            "summary": str(item.get("content", ""))[:800],
        })
    return {"query": query, "articles": articles[:max_results], "note": "Verificare le fonti originali prima di citare le notizie nell'omelia."}
