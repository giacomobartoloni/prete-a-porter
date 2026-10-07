"""
SQLite cache for liturgical data.

Implements caching of liturgical readings with TTL-based expiration.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from .scrapers import ScraperError, assert_complete_mass_reading
from .state import LiturgicalReading


# SQLite julianday comparison after normalizing legacy 'T' timestamps.
_VALID_EXPIRY_SQL = "julianday(replace(expires_at, 'T', ' ')) > julianday('now')"
_EXPIRED_OR_INVALID_SQL = (
    "expires_at IS NULL OR "
    "julianday(replace(expires_at, 'T', ' ')) IS NULL OR "
    "julianday(replace(expires_at, 'T', ' ')) <= julianday('now')"
)


class LiturgyCache:
    """
    SQLite-based cache for liturgical readings.

    Implements automatic TTL-based expiration (default: 24 hours).
    Provides fast retrieval of previously fetched readings.
    """

    DEFAULT_TTL_SECONDS = 24 * 3600

    def __init__(self, db_path: str | None = None) -> None:
        """
        Initialize cache with database path.

        Args:
            db_path: Path to SQLite database file. Defaults to DATABASE_PATH
                     env var, or /app/data/liturgy_cache.db if unset.
        """
        self.db_path = db_path or os.getenv("DATABASE_PATH", "/app/data/liturgy_cache.db")
        ttl_seconds = os.getenv("CACHE_TTL_SECONDS")
        if ttl_seconds:
            self.default_ttl_seconds = int(ttl_seconds)
        else:
            self.default_ttl_seconds = self.DEFAULT_TTL_SECONDS
        # Legacy alias for callers that still read hours.
        self.default_ttl_hours = self.default_ttl_seconds / 3600
        self.conn = None
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create database and schema if they don't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS liturgical_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                occasion TEXT NOT NULL,
                data TEXT NOT NULL,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                source TEXT DEFAULT 'cache'
            )
        ''')
        self.conn.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_date_occasion
            ON liturgical_cache(date, occasion)
        ''')
        self.conn.commit()

    def get(self, date: str, occasion: str) -> Optional[LiturgicalReading]:
        """
        Retrieve reading from cache if not expired and structurally complete.

        Invalid/poisoned rows are treated as misses and removed.
        """
        cursor = self.conn.execute(
            f'''
            SELECT data FROM liturgical_cache
            WHERE date = ? AND occasion = ?
            AND {_VALID_EXPIRY_SQL}
            ''',
            (date, occasion),
        )

        row = cursor.fetchone()
        if not row:
            return None

        try:
            data = json.loads(row[0])
            reading = LiturgicalReading(**data)
            assert_complete_mass_reading(reading)
            return reading
        except (TypeError, ValueError, ValidationError, json.JSONDecodeError, ScraperError):
            self.invalidate(date, occasion)
            return None

    def set(
        self,
        reading: LiturgicalReading,
        ttl_hours: float | int | None = None
    ) -> None:
        """
        Store reading in cache.

        Args:
            reading: LiturgicalReading to cache
            ttl_hours: Optional legacy TTL in hours (supports fractions).
                       When omitted, CACHE_TTL_SECONDS / default seconds apply.
        """
        assert_complete_mass_reading(reading)
        if ttl_hours is not None:
            ttl_seconds = int(float(ttl_hours) * 3600)
        else:
            ttl_seconds = self.default_ttl_seconds
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = now + timedelta(seconds=ttl_seconds)
        data = reading.model_dump_json()

        self.conn.execute('''
            INSERT OR REPLACE INTO liturgical_cache
            (date, occasion, data, cached_at, expires_at, source)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            reading.date,
            reading.occasion,
            data,
            now.strftime("%Y-%m-%d %H:%M:%S"),
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            'cache',
        ))
        self.conn.commit()

    def invalidate(self, date: str, occasion: str) -> None:
        """
        Remove specific entry from cache.

        Args:
            date: ISO format date
            occasion: Type of occasion
        """
        self.conn.execute('''
            DELETE FROM liturgical_cache
            WHERE date = ? AND occasion = ?
        ''', (date, occasion))
        self.conn.commit()

    def clear_expired(self) -> int:
        """
        Remove all expired or malformed-expiry entries.

        Returns:
            Number of entries removed
        """
        cursor = self.conn.execute(
            f'''
            DELETE FROM liturgical_cache
            WHERE {_EXPIRED_OR_INVALID_SQL}
            '''
        )
        self.conn.commit()
        return cursor.rowcount

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache_size, valid_entries, and expired_entries
        """
        cursor = self.conn.execute('SELECT COUNT(*) FROM liturgical_cache')
        total = cursor.fetchone()[0]

        cursor = self.conn.execute(
            f'''
            SELECT COUNT(*) FROM liturgical_cache
            WHERE {_VALID_EXPIRY_SQL}
            '''
        )
        valid = cursor.fetchone()[0]

        return {
            'cache_size': total,
            'valid_entries': valid,
            'expired_entries': total - valid
        }
