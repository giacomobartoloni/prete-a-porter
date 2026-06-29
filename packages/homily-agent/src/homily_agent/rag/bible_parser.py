import re
import logging
from dataclasses import dataclass
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)


@dataclass
class Verse:
    book: str
    abbreviation: str
    chapter: int
    verse: int
    text: str
    testament: str
    section: str
    book_type: str


@dataclass
class BibleChunk:
    id: str
    text: str
    metadata: dict


BOOK_METADATA: dict[str, dict] = {
    "GENESI": {"abb": "Gen", "section": "Pentateuco", "testament": "AT", "type": "narrative"},
    "ESODO": {"abb": "Es", "section": "Pentateuco", "testament": "AT", "type": "narrative"},
    "LEVITICO": {"abb": "Lv", "section": "Pentateuco", "testament": "AT", "type": "law"},
    "NUMERI": {"abb": "Nm", "section": "Pentateuco", "testament": "AT", "type": "narrative"},
    "DEUTERONOMIO": {"abb": "Dt", "section": "Pentateuco", "testament": "AT", "type": "law"},
    "GIOSUÈ": {"abb": "Gs", "section": "Storici", "testament": "AT", "type": "narrative"},
    "GIUDICI": {"abb": "Gdc", "section": "Storici", "testament": "AT", "type": "narrative"},
    "RUT": {"abb": "Rt", "section": "Storici", "testament": "AT", "type": "narrative"},
    "SAMUELE 1": {"abb": "1Sam", "section": "Storici", "testament": "AT", "type": "narrative"},
    "SAMUELE 2": {"abb": "2Sam", "section": "Storici", "testament": "AT", "type": "narrative"},
    "RE 1": {"abb": "1Re", "section": "Storici", "testament": "AT", "type": "narrative"},
    "RE 2": {"abb": "2Re", "section": "Storici", "testament": "AT", "type": "narrative"},
    "CRONACHE 1": {"abb": "1Cr", "section": "Storici", "testament": "AT", "type": "narrative"},
    "CRONACHE 2": {"abb": "2Cr", "section": "Storici", "testament": "AT", "type": "narrative"},
    "ESDRA": {"abb": "Esd", "section": "Storici", "testament": "AT", "type": "narrative"},
    "NEEMIA": {"abb": "Ne", "section": "Storici", "testament": "AT", "type": "narrative"},
    "TOBIA": {"abb": "Tb", "section": "Storici", "testament": "AT", "type": "narrative"},
    "GIUDITTA": {"abb": "Gdt", "section": "Storici", "testament": "AT", "type": "narrative"},
    "ESTER": {"abb": "Est", "section": "Storici", "testament": "AT", "type": "narrative"},
    "MACCABEI 1": {"abb": "1Mac", "section": "Storici", "testament": "AT", "type": "narrative"},
    "MACCABEI 2": {"abb": "2Mac", "section": "Storici", "testament": "AT", "type": "narrative"},
    "GIOBBE": {"abb": "Gb", "section": "Poetici e Sapienziali", "testament": "AT", "type": "poetry"},
    "LIBRO DEI SALMI": {"abb": "Sal", "section": "Poetici e Sapienziali", "testament": "AT", "type": "poetry"},
    "PROVERBI": {"abb": "Pr", "section": "Poetici e Sapienziali", "testament": "AT", "type": "poetry"},
    "QOÈLET": {"abb": "Qo", "section": "Poetici e Sapienziali", "testament": "AT", "type": "poetry"},
    "CANTICO DEI CANTICI": {"abb": "Ct", "section": "Poetici e Sapienziali", "testament": "AT", "type": "poetry"},
    "SAPIENZA": {"abb": "Sap", "section": "Poetici e Sapienziali", "testament": "AT", "type": "poetry"},
    "SIRACIDE": {"abb": "Sir", "section": "Poetici e Sapienziali", "testament": "AT", "type": "poetry"},
    "LIBRO DEL PROFETA ISAIA": {"abb": "Is", "section": "Profeti", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA GEREMIA": {"abb": "Ger", "section": "Profeti", "testament": "AT", "type": "prophecy"},
    "LIBRO DELLE LAMENTAZIONI": {"abb": "Lam", "section": "Profeti", "testament": "AT", "type": "poetry"},
    "LIBRO DEL PROFETA BARUC": {"abb": "Bar", "section": "Profeti", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA EZECHIELE": {"abb": "Ez", "section": "Profeti", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA DANIELE": {"abb": "Dn", "section": "Profeti", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA OSEA": {"abb": "Os", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA GIOELE": {"abb": "Gl", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA AMOS": {"abb": "Am", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA ABDIA": {"abb": "Abd", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA GIONA": {"abb": "Gn", "section": "Profeti minori", "testament": "AT", "type": "narrative"},
    "LIBRO DEL PROFETA MICHEA": {"abb": "Mi", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA NAUM": {"abb": "Na", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA ABACUC": {"abb": "Ab", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA SOFONIA": {"abb": "Sof", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA AGGEO": {"abb": "Ag", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA ZACCARIA": {"abb": "Zc", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "LIBRO DEL PROFETA MALACHIA": {"abb": "Ml", "section": "Profeti minori", "testament": "AT", "type": "prophecy"},
    "VANGELO SECONDO MATTEO": {"abb": "Mt", "section": "Vangeli", "testament": "NT", "type": "gospel"},
    "VANGELO SECONDO MARCO": {"abb": "Mc", "section": "Vangeli", "testament": "NT", "type": "gospel"},
    "VANGELO SECONDO LUCA": {"abb": "Lc", "section": "Vangeli", "testament": "NT", "type": "gospel"},
    "VANGELO SECONDO GIOVANNI": {"abb": "Gv", "section": "Vangeli", "testament": "NT", "type": "gospel"},
    "ATTI DEGLI APOSTOLI": {"abb": "At", "section": "Storici", "testament": "NT", "type": "narrative"},
    "LETTERA AI ROMANI": {"abb": "Rm", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "PRIMA LETTERA AI CORINZI": {"abb": "1Cor", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "SECONDA LETTERA AI CORINZI": {"abb": "2Cor", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "LETTERA AI GÀLATI": {"abb": "Gal", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "LETTERA AGLI EFESINI": {"abb": "Ef", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "LETTERA AI FILIPPESI": {"abb": "Fil", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "LETTERA AI COLOSSESI": {"abb": "Col", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "PRIMA LETTERA AI TESSALONICESI": {"abb": "1Ts", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "SECONDA LETTERA AI TESSALONICESI": {"abb": "2Ts", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "PRIMA LETTERA A TIMÒTEO": {"abb": "1Tm", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "SECONDA LETTERA A TIMÒTEO": {"abb": "2Tm", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "LETTERA A TITO": {"abb": "Tt", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "LETTERA A FILÈMONE": {"abb": "Fm", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "LETTERA AGLI EBREI": {"abb": "Eb", "section": "Lettere di Paolo", "testament": "NT", "type": "letter"},
    "LETTERA DI GIACOMO": {"abb": "Gc", "section": "Lettere cattoliche", "testament": "NT", "type": "letter"},
    "PRIMA LETTERA DI PIETRO": {"abb": "1Pt", "section": "Lettere cattoliche", "testament": "NT", "type": "letter"},
    "SECONDA LETTERA DI PIETRO": {"abb": "2Pt", "section": "Lettere cattoliche", "testament": "NT", "type": "letter"},
    "PRIMA LETTERA DI GIOVANNI": {"abb": "1Gv", "section": "Lettere cattoliche", "testament": "NT", "type": "letter"},
    "SECONDA LETTERA DI GIOVANNI": {"abb": "2Gv", "section": "Lettere cattoliche", "testament": "NT", "type": "letter"},
    "TERZA LETTERA DI GIOVANNI": {"abb": "3Gv", "section": "Lettere cattoliche", "testament": "NT", "type": "letter"},
    "LETTERA DI GIUDA": {"abb": "Gd", "section": "Lettere cattoliche", "testament": "NT", "type": "letter"},
    "LIBRO DELL\u2019APOCALISSE": {"abb": "Ap", "section": "Apocalisse", "testament": "NT", "type": "prophecy"},
}


class BibleParser:
    def __init__(self, html_dir: str):
        self.html_dir = Path(html_dir)
        if BeautifulSoup is None:
            raise ImportError(
                "beautifulsoup4 is required. Install with: pip install beautifulsoup4"
            )

    def parse_all(self) -> list[Verse]:
        verses: list[Verse] = []
        for path in sorted(self.html_dir.glob("*.htm")):
            try:
                verses.extend(self.parse_file(path))
            except Exception as e:
                logger.warning(f"Error parsing {path}: {e}")
        return verses

    def parse_file(self, path: Path) -> list[Verse]:
        html = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        raw_book = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""
        book = raw_book.strip().upper()
        meta = BOOK_METADATA.get(book, {})
        abbreviation = meta.get("abb", "")
        testament = meta.get("testament", "")
        section = meta.get("section", "")
        book_type = meta.get("type", "")

        verses: list[Verse] = []
        seen: set[tuple[int, int]] = set()
        for a_tag in soup.find_all("a", href=lambda h: h and h.startswith("#cap_")):
            target = a_tag.get("href", "").lstrip("#")
            chapter = self._chapter_from_anchor(target)
            chapter_verses = self._extract_chapter_verses(soup, target, chapter)
            for v in chapter_verses:
                key = (v["chapter"], v["verse"])
                if key not in seen:
                    seen.add(key)
                    verses.append(Verse(
                        book=book, abbreviation=abbreviation, chapter=v["chapter"],
                        verse=v["verse"], text=v["text"],
                        testament=testament, section=section, book_type=book_type,
                    ))
        return verses

    @staticmethod
    def _chapter_from_anchor(anchor: str) -> int:
        parts = anchor.split("_")
        last = 0
        for p in parts:
            if p.isdigit():
                last = int(p)
        return last

    @staticmethod
    def _extract_chapter_verses(soup, chapter_anchor: str, chapter: int) -> list[dict]:
        anchor = soup.find("a", attrs={"name": chapter_anchor})
        if not anchor:
            return []
        h2 = anchor.find_parent("h2")
        if not h2:
            return []
        verses: list[dict] = []
        current = h2.find_next_sibling()
        while current and current.name != "h2":
            if current.name == "p":
                text = str(current)
                verse_numbers = re.findall(r'<sup><b>(\d+)</b></sup>', text)
                texts = re.split(r'<sup><b>\d+</b></sup>', text)
                for i, vn in enumerate(verse_numbers):
                    idx = i + 1
                    if idx < len(texts):
                        plain = BeautifulSoup(texts[idx], "html.parser").get_text(" ", strip=True)
                        if plain:
                            verses.append({"chapter": chapter, "verse": int(vn), "text": plain})
            current = current.find_next_sibling()
        return verses


class Chunker:
    MAX_CHARS = 2000
    OVERLAP_VERSES = 2

    def chunk_verses(self, verses: list[Verse]) -> list[BibleChunk]:
        chapters: dict[tuple[str, int], list[Verse]] = {}
        for v in verses:
            chapters.setdefault((v.book, v.chapter), []).append(v)

        chunks: list[BibleChunk] = []
        for (book, chapter), chapter_verses in chapters.items():
            full_text = self._join_verses(chapter_verses)
            if len(full_text) <= self.MAX_CHARS:
                chunks.append(self._make_chunk(chapter_verses))
            else:
                chunks.extend(self._sub_chunk(chapter_verses))
        return chunks

    @staticmethod
    def _join_verses(verses: list[Verse]) -> str:
        return " ".join(v.text for v in verses)

    def _make_chunk(self, verses: list[Verse]) -> BibleChunk:
        v = verses[0]
        last = verses[-1]
        chunk_id = f"bibbia_{v.abbreviation}_{v.chapter}_{v.verse}_{last.verse}"
        return BibleChunk(
            id=chunk_id,
            text=self._join_verses(verses),
            metadata={
                "source": "Bible",
                "book": v.book,
                "abbreviation": v.abbreviation,
                "chapter": v.chapter,
                "verse_start": v.verse,
                "verse_end": last.verse,
                "testament": v.testament,
                "section": v.section,
                "book_type": v.book_type,
            }
        )

    def _sub_chunk(self, verses: list[Verse]) -> list[BibleChunk]:
        chunks: list[BibleChunk] = []
        buf: list[Verse] = []
        for v in verses:
            test_text = self._join_verses(buf + [v])
            if len(test_text) > self.MAX_CHARS and buf:
                chunks.append(self._make_chunk(buf))
                overlap = max(0, len(buf) - self.OVERLAP_VERSES)
                buf = buf[overlap:]
            buf.append(v)
        if buf:
            chunks.append(self._make_chunk(buf))
        return chunks
