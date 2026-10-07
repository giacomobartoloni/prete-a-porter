"""Cache TTL uses consistent numeric datetime comparison and seconds precision."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from liturgy_agent.cache import LiturgyCache
from liturgy_agent.state import LiturgicalMetadata, LiturgicalReading, Reading


def _reading() -> LiturgicalReading:
    date = "2026-05-19"
    return LiturgicalReading(
        date=date,
        occasion="mass",
        metadata=LiturgicalMetadata(
            date=date,
            occasion="mass",
            season="Ordinary",
            color="Green",
            year_cycle="A",
            sunday_or_weekday="Weekday",
        ),
        first_reading=Reading(reference="A 1", text="a", type="First"),
        psalm=Reading(reference="B 1", text="b", type="Psalm"),
        gospel=Reading(reference="C 1", text="c", type="Gospel"),
        cached_at=datetime(2026, 5, 19, 12, 0, 0),
        source="test",
    )


def _insert_raw(cache: LiturgyCache, expires_at: str) -> None:
    cache.conn.execute(
        """
        INSERT OR REPLACE INTO liturgical_cache
        (date, occasion, data, cached_at, expires_at, source)
        VALUES (?, ?, ?, datetime('now'), ?, 'cache')
        """,
        ("2026-05-19", "mass", _reading().model_dump_json(), expires_at),
    )
    cache.conn.commit()


def test_cache_hit_before_expiry(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_TTL_SECONDS", "3600")
    cache = LiturgyCache(db_path=str(tmp_path / "c.db"))
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_raw(cache, future)
    assert cache.get("2026-05-19", "mass") is not None


def test_cache_miss_at_exact_expiry_boundary(tmp_path) -> None:
    cache = LiturgyCache(db_path=str(tmp_path / "c.db"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    _insert_raw(cache, now)
    assert cache.get("2026-05-19", "mass") is None


def test_cache_miss_after_expiry(tmp_path) -> None:
    cache = LiturgyCache(db_path=str(tmp_path / "c.db"))
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_raw(cache, past)
    assert cache.get("2026-05-19", "mass") is None


def test_legacy_t_and_space_timestamp_formats(tmp_path) -> None:
    cache = LiturgyCache(db_path=str(tmp_path / "c.db"))
    future_t = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
    _insert_raw(cache, future_t)
    assert cache.get("2026-05-19", "mass") is not None

    cache.invalidate("2026-05-19", "mass")
    future_space = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_raw(cache, future_space)
    assert cache.get("2026-05-19", "mass") is not None


def test_malformed_expiry_is_unusable_and_cleanable(tmp_path) -> None:
    cache = LiturgyCache(db_path=str(tmp_path / "c.db"))
    _insert_raw(cache, "not-a-timestamp")
    assert cache.get("2026-05-19", "mass") is None
    removed = cache.clear_expired()
    assert removed >= 1
    assert cache.get_stats()["cache_size"] == 0


def test_fractional_hour_ttl_seconds(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_TTL_SECONDS", "1800")  # 30 minutes
    cache = LiturgyCache(db_path=str(tmp_path / "c.db"))
    assert cache.default_ttl_seconds == 1800
    cache.set(_reading())
    row = cache.conn.execute(
        "SELECT expires_at, cached_at FROM liturgical_cache WHERE date=?",
        ("2026-05-19",),
    ).fetchone()
    expires_at = datetime.fromisoformat(row[0].replace("T", " "))
    cached_at = datetime.fromisoformat(row[1].replace("T", " "))
    delta = expires_at - cached_at
    assert 1700 <= delta.total_seconds() <= 1900


def test_legacy_explicit_ttl_hours_still_works(tmp_path) -> None:
    cache = LiturgyCache(db_path=str(tmp_path / "c.db"))
    cache.set(_reading(), ttl_hours=2)
    assert cache.get("2026-05-19", "mass") is not None


def test_stats_and_cleanup_agree_on_expiry(tmp_path) -> None:
    cache = LiturgyCache(db_path=str(tmp_path / "c.db"))
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_raw(cache, past)
    cache.conn.execute(
        """
        INSERT INTO liturgical_cache (date, occasion, data, cached_at, expires_at, source)
        VALUES (?, ?, ?, datetime('now'), ?, 'cache')
        """,
        ("2026-05-20", "mass", _reading().model_dump_json(), future),
    )
    cache.conn.commit()
    stats = cache.get_stats()
    assert stats["cache_size"] == 2
    assert stats["valid_entries"] == 1
    assert stats["expired_entries"] == 1
    assert cache.clear_expired() == 1
    assert cache.get_stats()["cache_size"] == 1
