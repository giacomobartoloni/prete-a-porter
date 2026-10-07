"""Date normalisation must always yield ISO before the liturgy agent sees it.

The liturgy agent accepts only YYYY-MM-DD. The model is asked to resolve
relative dates with ``calculate_date`` first, but it often passes the phrase
through — and ``calculate_date`` itself returns "Sunday, September 20, 2026",
which is not ISO either. This function is the last boundary covering both.
"""

import re
from datetime import datetime, timedelta

import pytest

from chat_orchestrator.tools import _normalize_date

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TestPassThrough:
    def test_iso_is_returned_unchanged(self):
        assert _normalize_date("2026-09-20") == "2026-09-20"

    def test_none_stays_none(self):
        assert _normalize_date(None) is None


class TestRelativeWords:
    @pytest.mark.parametrize("word", ["today", "oggi"])
    def test_today(self, word):
        assert _normalize_date(word) == datetime.now().strftime("%Y-%m-%d")

    @pytest.mark.parametrize("word", ["tomorrow", "domani"])
    def test_tomorrow(self, word):
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert _normalize_date(word) == expected

    @pytest.mark.parametrize("word", ["yesterday", "ieri"])
    def test_yesterday(self, word):
        expected = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert _normalize_date(word) == expected


class TestWeekdayPhrases:
    """The regression: 'next sunday' used to reach the liturgy agent verbatim."""

    @pytest.mark.parametrize("phrase", ["next sunday", "sunday", "domenica", "prossima domenica"])
    def test_sunday_phrases_resolve_to_a_sunday(self, phrase):
        result = _normalize_date(phrase)
        assert ISO.match(result), result
        assert datetime.strptime(result, "%Y-%m-%d").weekday() == 6

    def test_resolves_to_the_next_occurrence_not_today(self):
        """A weekday name always means the next one, never today."""
        result = _normalize_date("sunday")
        assert datetime.strptime(result, "%Y-%m-%d").date() > datetime.now().date()

    @pytest.mark.parametrize(
        "phrase,weekday",
        [("monday", 0), ("lunedì", 0), ("friday", 4), ("venerdì", 4), ("sabato", 5)],
    )
    def test_other_weekdays(self, phrase, weekday):
        result = _normalize_date(phrase)
        assert ISO.match(result), result
        assert datetime.strptime(result, "%Y-%m-%d").weekday() == weekday

    def test_weekday_inside_a_sentence(self):
        assert ISO.match(_normalize_date("the next sunday please"))


class TestReadableFormats:
    """calculate_date returns a long form; feeding it back must still work."""

    def test_long_form_with_weekday(self):
        target = datetime.now() + timedelta(days=7)
        readable = target.strftime("%A, %B %d, %Y")
        assert _normalize_date(readable) == target.strftime("%Y-%m-%d")

    def test_month_day_year(self):
        assert _normalize_date("September 20, 2026") == "2026-09-20"

    def test_slash_format(self):
        assert _normalize_date("20/09/2026") == "2026-09-20"


class TestUnparseable:
    def test_unknown_input_is_returned_as_is(self):
        """Better a downstream error than a silently substituted date."""
        assert _normalize_date("quando capita") == "quando capita"
