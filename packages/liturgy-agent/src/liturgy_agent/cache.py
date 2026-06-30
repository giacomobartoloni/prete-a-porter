"""
SQLite cache for liturgical data.

Implements caching of liturgical readings with TTL-based expiration.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from .state import LiturgicalReading


class LiturgyCache:
    """
    SQLite-based cache for liturgical readings.
    
    Implements automatic TTL-based expiration (default: 24 hours).
    Provides fast retrieval of previously fetched readings.
    """
    
    DEFAULT_TTL_HOURS = 24
    
    def __init__(self, db_path: str | None = None) -> None:
        """
        Initialize cache with database path.

        Args:
            db_path: Path to SQLite database file. Defaults to DATABASE_PATH
                     env var, or /app/data/liturgy_cache.db if unset.
        """
        self.db_path = db_path or os.getenv("DATABASE_PATH", "/app/data/liturgy_cache.db")
        ttl_seconds = os.getenv("CACHE_TTL_SECONDS")
        self.default_ttl_hours = int(ttl_seconds) // 3600 if ttl_seconds else self.DEFAULT_TTL_HOURS
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
        Retrieve reading from cache if not expired.
        
        Args:
            date: ISO format date (YYYY-MM-DD)
            occasion: Type of occasion (mass, marriage, baptism, funeral)
            
        Returns:
            LiturgicalReading if found and not expired, None otherwise
        """
        cursor = self.conn.execute('''
            SELECT data FROM liturgical_cache
            WHERE date = ? AND occasion = ?
            AND expires_at > datetime('now')
        ''', (date, occasion))
        
        row = cursor.fetchone()
        if row:
            data = json.loads(row[0])
            return LiturgicalReading(**data)
        
        return None
    
    def set(
        self,
        reading: LiturgicalReading,
        ttl_hours: int | None = None
    ) -> None:
        """
        Store reading in cache.
        
        Args:
            reading: LiturgicalReading to cache
            ttl_hours: Time-to-live in hours (default: from env or 24)
        """
        ttl = ttl_hours if ttl_hours is not None else self.default_ttl_hours
        expires_at = datetime.utcnow() + timedelta(hours=ttl)
        data = reading.model_dump_json()  # Uses Pydantic v2 with datetime serialization
        
        self.conn.execute('''
            INSERT OR REPLACE INTO liturgical_cache
            (date, occasion, data, cached_at, expires_at, source)
            VALUES (?, ?, ?, datetime('now'), ?, ?)
        ''', (reading.date, reading.occasion, data, expires_at.isoformat(), 'cache'))
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
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        cursor = self.conn.execute('''
            DELETE FROM liturgical_cache
            WHERE expires_at <= datetime('now')
        ''')
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
        
        cursor = self.conn.execute('''
            SELECT COUNT(*) FROM liturgical_cache
            WHERE expires_at > datetime('now')
        ''')
        valid = cursor.fetchone()[0]
        
        return {
            'cache_size': total,
            'valid_entries': valid,
            'expired_entries': total - valid
        }
