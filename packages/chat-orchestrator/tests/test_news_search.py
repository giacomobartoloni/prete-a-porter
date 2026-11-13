"""Tavily boundary regression tests use mocked HTTP with no real provider calls."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from chat_orchestrator import news


def _article(url="https://example.org/valid", published_date=None):
    if published_date is None:
        published_date = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    return {
        "url": url,
        "title": "Notizia di prova",
        "published_date": published_date,
        "content": "Contenuto verificabile sul sito originale",
    }


async def _invoke(monkeypatch, results):
    monkeypatch.setenv("TAVILY_API_KEY", "test-only-key")
    original_client = httpx.AsyncClient

    async def respond(request):
        return httpx.Response(200, json={"results": results}, request=request)

    def fake_client(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(news.httpx, "AsyncClient", fake_client)
    return await news.search_news.ainvoke({"query": "pace", "days_back": 7})


@pytest.mark.parametrize("malformed", [
    None,
    {"url": 123, "published_date": "2026-11-09"},
    {"url": "https://example.org/bad", "published_date": 123},
    {"url": "https://[not-valid-ipv6", "published_date": "2026-11-09"},
])
async def test_malformed_article_does_not_discard_valid_siblings(monkeypatch, malformed):
    result = await _invoke(monkeypatch, [
        _article(), malformed, _article("https://example.org/second"),
    ])
    assert [article["url"] for article in result["articles"]] == [
        "https://example.org/valid", "https://example.org/second",
    ]


@pytest.mark.parametrize("date_value", [
    lambda date: date.isoformat(),
    lambda date: date.date().isoformat(),
    lambda date: date.strftime("%a, %d %b %Y %H:%M:%S GMT"),
])
async def test_documented_publication_date_formats_are_accepted(monkeypatch, date_value):
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    result = await _invoke(monkeypatch, [_article(published_date=date_value(recent))])
    assert len(result["articles"]) == 1
    assert result["articles"][0]["published_at"] == recent.date().isoformat()


async def test_undated_or_invalid_dates_are_excluded_individually(monkeypatch):
    result = await _invoke(monkeypatch, [
        _article("https://example.org/missing", published_date=""),
        _article("https://example.org/invalid", published_date="not a date"),
        _article(
            "https://example.org/rfc",
            published_date=(datetime.now(timezone.utc) - timedelta(hours=1))
                .strftime("%a, %d %b %Y %H:%M:%S GMT"),
        ),
    ])
    assert [article["url"] for article in result["articles"]] == ["https://example.org/rfc"]
