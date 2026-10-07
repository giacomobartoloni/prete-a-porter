"""
Web scraping module for retrieving liturgical data from Catholic sources.

This module provides scrapers for:
- evangelizo.org: Daily Gospel readings and liturgical information

Error handling includes automatic retries and graceful
degradation to lectionary data when web services are unavailable.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import re
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class ScraperError(Exception):
    """Base exception for web scraping errors."""
    pass


def assert_complete_mass_reading(reading: "LiturgicalReading") -> "LiturgicalReading":
    """Require nonblank first reading, psalm, and gospel; weekday second may be absent.

    A present second reading must also have nonblank reference and text.
    """
    from .state import LiturgicalReading  # local import for type/runtime check

    if not isinstance(reading, LiturgicalReading):
        raise ScraperError("Incomplete Mass readings: expected LiturgicalReading")

    required = (
        ("first_reading", reading.first_reading),
        ("psalm", reading.psalm),
        ("gospel", reading.gospel),
    )
    for name, entry in required:
        if entry is None:
            raise ScraperError(f"Incomplete Mass readings: missing required {name}")
        ref = (entry.reference or "").strip()
        text = (entry.text or "").strip()
        if not ref or not text:
            raise ScraperError(
                f"Incomplete Mass readings: required {name} has blank reference or text"
            )

    if reading.second_reading is not None:
        ref = (reading.second_reading.reference or "").strip()
        text = (reading.second_reading.text or "").strip()
        if not ref or not text:
            raise ScraperError(
                "Incomplete Mass readings: second_reading is present but incomplete"
            )
    return reading


class EvangelizeScraper:
    """
    Scraper for evangelizo.org - official Vatican daily readings source.
    
    Provides:
    - Daily Gospel reading
    - Gospel commentary
    - Feast information
    """
    
    BASE_URL = "https://vangelodelgiorno.org"
    API_BASE_URL = "https://publication.evangelizo.ws"
    LANG_CODE = "IT"
    TIMEOUT = 10
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    
    def __init__(self):
        """Initialize the Evangelizo scraper."""
        if not HAS_HTTPX:
            raise ScraperError(
                "httpx is required for Evangelizo scraper. "
                "Install with: pip install httpx"
            )
        if not HAS_BS4:
            logger.warning("beautifulsoup4 not available; HTML fallback disabled")
    
    async def fetch_daily_gospel(self, date: Optional[datetime] = None) -> dict:
        """
        Fetch daily Gospel reading from evangelizo.org.
        
        Args:
            date: Target date (defaults to today)
            
        Returns:
            Dictionary with Gospel text, reference, commentary
            
        Raises:
            ScraperError: If scraping fails after retries
        """
        if date is None:
            date = datetime.now()
        
        # Format: YYYY-MM-DD
        date_str = date.strftime("%Y-%m-%d")
        api_url = (
            f"{self.API_BASE_URL}/{self.LANG_CODE}/days/{date_str}"
            "?include=readings,commentary"
        )
        
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    logger.info(
                        "Scraping request: GET %s (attempt %s/%s)",
                        api_url,
                        attempt + 1,
                        self.MAX_RETRIES
                    )
                    response = await client.get(api_url, follow_redirects=True)
                    logger.info(
                        "Scraping response: %s %s",
                        response.status_code,
                        api_url
                    )
                    response.raise_for_status()

                    payload = response.json()
                    return self._parse_daily_gospel_api(payload, date_str)
            
            except (httpx.HTTPError, httpx.RequestError, OSError) as e:
                logger.warning(
                    "Scraping error: %s (attempt %s/%s)",
                    e,
                    attempt + 1,
                    self.MAX_RETRIES
                )
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue
                raise ScraperError(
                    f"Failed to fetch from {api_url} after {self.MAX_RETRIES} attempts: {e}"
                ) from e
        
        raise ScraperError("Unexpected error in Evangelizo scraper")

    def _parse_daily_gospel_api(self, payload: dict, date_str: str) -> dict:
        """
        Parse JSON payload from publication.evangelizo.ws.

        Expected structure:
            data.readings[]  – list of readings with book_type in
                               {"reading", "psalm", "gospel"}
            data.liturgy     – liturgical title/description
            data.commentary  – daily commentary with author
        """
        data = payload.get("data", payload)
        readings = data.get("readings", [])

        # Strip inline verse markers such as [[Ex 17,3]]
        def _strip_markers(text: str) -> str:
            return re.sub(r'\[\[.*?\]\]', '', text or "").strip()

        def _parse_entry(r: dict) -> dict:
            book = r.get("book") or {}
            book_title = book.get("full_title") or ""
            reference_displayed = r.get("reference_displayed") or ""
            reference = f"{book_title} {reference_displayed}".strip()
            return {
                "reference": reference,
                "reading_code": r.get("reading_code") or "",
                "title": r.get("title") or book_title,
                "text": _strip_markers(r.get("text")),
                "audio_url": r.get("audio_url"),
            }

        # Separate readings by book_type, preserving document order
        plain_readings = [r for r in readings if r.get("book_type") == "reading"]
        psalm_entry   = next((r for r in readings if r.get("book_type") == "psalm"), None)
        gospel_entry  = next((r for r in readings if r.get("book_type") == "gospel"), None)

        if not gospel_entry:
            raise ScraperError(f"No gospel reading found for {date_str}")
        if not plain_readings:
            raise ScraperError(f"No first reading found for {date_str}")
        if not psalm_entry:
            raise ScraperError(f"No psalm reading found for {date_str}")

        first_reading  = _parse_entry(plain_readings[0])
        second_reading = _parse_entry(plain_readings[1]) if len(plain_readings) >= 2 else None
        psalm = _parse_entry(psalm_entry)
        psalm["chorus"] = psalm_entry.get("chorus") or ""
        gospel = _parse_entry(gospel_entry)

        for name, entry in (
            ("first_reading", first_reading),
            ("psalm", psalm),
            ("gospel", gospel),
        ):
            if not (entry.get("reference") or "").strip() or not (entry.get("text") or "").strip():
                raise ScraperError(
                    f"Incomplete Mass readings from upstream: blank {name} for {date_str}"
                )

        # Liturgical metadata
        liturgy_block  = data.get("liturgy") or {}
        liturgic_title = data.get("liturgic_title") or liturgy_block.get("title") or ""
        date_displayed = data.get("date_displayed") or ""

        # Commentary
        commentary_text   = ""
        commentary_author = ""
        commentary_source = ""
        commentary_data = data.get("commentary")
        if commentary_data:
            commentary_text   = _strip_markers(commentary_data.get("description"))
            commentary_source = commentary_data.get("source") or ""
            author = commentary_data.get("author") or {}
            commentary_author = author.get("name") or ""

        result: dict = {
            "source": "evangelizo.ws",
            "date": date_str,
            "date_displayed": date_displayed,
            "liturgic_title": liturgic_title,
            # Top-level gospel fields kept for backward compatibility
            "gospel_reference": gospel["reference"],
            "gospel_text": gospel["text"],
            "commentary": commentary_text,
            "commentary_author": commentary_author,
            "commentary_source": commentary_source,
            "scraped_at": datetime.now().isoformat(),
        }

        result["first_reading"] = first_reading
        result["psalm"] = psalm
        if second_reading:
            result["second_reading"] = second_reading
        result["gospel"] = gospel

        return result


async def fetch_liturgical_data(
    date: Optional[datetime] = None,
    include_evangelizo: bool = True
) -> dict:
    """
    Fetch liturgical data from available sources.
    
    This is the main entry point for web scraping.
    
    Args:
        date: Target date (defaults to today)
        include_evangelizo: Whether to scrape evangelizo.org
        
    Returns:
        Dictionary with all available liturgical data
    """
    if date is None:
        date = datetime.now()

    logger.info(f"[fetch_liturgical_data] Start: date={date.strftime('%Y-%m-%d')}, include_evangelizo={include_evangelizo}")

    tasks = []

    if include_evangelizo:
        try:
            logger.info("[fetch_liturgical_data] Adding Evangelizo scraper task")
            scraper = EvangelizeScraper()
            tasks.append(scraper.fetch_daily_gospel(date))
        except ScraperError as e:
            logger.warning(f"[fetch_liturgical_data] Evangelizo scraper unavailable: {e}")

    if not tasks:
        logger.error("[fetch_liturgical_data] No scrapers available. Aborting.")
        raise ScraperError(
            "No scrapers available. Install httpx and beautifulsoup4"
        )

    logger.info(f"[fetch_liturgical_data] Running {len(tasks)} scraper tasks in parallel")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged = {
        "date": date.strftime("%Y-%m-%d"),
        "sources": {}
    }

    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"[fetch_liturgical_data] Scraper task failed: {result}")
            continue  # Skip failed sources

        source_name = result.get("source", "unknown")
        logger.info(f"[fetch_liturgical_data] Merged result from source: {source_name}")
        merged["sources"][source_name] = result

    logger.info(f"[fetch_liturgical_data] Returning merged result with sources: {list(merged['sources'].keys())}")
    return merged
