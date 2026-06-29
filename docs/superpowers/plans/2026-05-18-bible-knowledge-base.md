# Bible Knowledge Base — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate ChromaDB `corpus` collection with Bibbia CEI 2008 (73 HTML files) and Catechismo della Chiesa Cattolica (PDF) for semantic retrieval during homily generation.

**Architecture:** Two parsers (`BibleParser`, `CatechismParser`) produce normalized chunks → shared `Chunker` → `RetrievalService.add_documents("corpus")`. A single CLI script orchestrates ingestion.

**Tech Stack:** Python 3.12, BeautifulSoup4, PyMuPDF, ChromaDB (ml extras), pytest

---

### File Structure

| Path | Type | Responsibility |
|---|---|---|
| `src/homily_agent/rag/bible_parser.py` | Create | `Verse` dataclass, `BibleParser`, `Chunker`, book metadata maps |
| `src/homily_agent/rag/catechism_parser.py` | Create | `Paragraph` dataclass, `CatechismParser` |
| `src/homily_agent/rag/__init__.py` | Modify | Export `BibleParser`, `CatechismParser`, `Chunker` |
| `src/homily_agent/rag/retrieval.py` | Modify | Update `persist_directory` to `data/chroma_db`, add `reset_collection` |
| `scripts/ingest_corpus.py` | Create | CLI orchestrator: parse → chunk → ChromaDB |
| `pyproject.toml` | Modify | Add `pymupdf`, `beautifulsoup4`, `lxml` as ml deps |
| `tests/rag/test_bible_parser.py` | Create | Unit tests for Bible parsing + chunking |
| `tests/rag/test_catechism_parser.py` | Create | Unit tests for CCC parsing |

---

### Task 1: Update RetrievalService

**Files:**
- Modify: `packages/homily-agent/src/homily_agent/rag/retrieval.py:51-56`
- Test: will be covered by integration test

- [ ] **Step 1: Change default collection_name and persist_directory**

Change the defaults in `RetrievalService.__init__`:
- `collection_name: str = "corpus"` (was `"theological_corpus"`)
- `persist_directory: str = "data/chroma_db"` (was `"backend/data/chroma_db"`)

```python
    def __init__(
        self,
        persist_directory: str = "data/chroma_db",
        collection_name: str = "corpus",
        top_k: int = 5,
        min_similarity: float = 0.7
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.top_k = top_k
        self.min_similarity = min_similarity
```

- [ ] **Step 2: Add `reset_collection` method**

Add before `get_document_count`:

```python
    def reset_collection(self) -> None:
        self._ensure_initialized()
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.create_collection(
            self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Reset collection: {self.collection_name}")
```

- [ ] **Step 3: Update `load_theological_corpus` default path**

Change line 183 from `corpus_directory = "backend/data/theological_corpus"` to `corpus_directory = "data/theological_corpus"`.

---

### Task 2: Create Bible Parser

**Files:**
- Create: `packages/homily-agent/src/homily_agent/rag/bible_parser.py`
- Create: `packages/homily-agent/tests/rag/test_bible_parser.py`

- [ ] **Step 1: Write test for Verse dataclass**

Create `packages/homily-agent/tests/rag/test_bible_parser.py`:

```python
import pytest
from homily_agent.rag.bible_parser import Verse, BibleChunk, BookMetadata


class TestVerse:
    def test_verse_creation(self):
        v = Verse(
            book="Genesi", abbreviation="Gen", chapter=1, verse=1,
            text="In principio Dio creò il cielo e la terra.",
            testament="AT", section="Pentateuco", book_type="narrative"
        )
        assert v.book == "Genesi"
        assert v.abbreviation == "Gen"
        assert v.chapter == 1
        assert v.verse == 1


class TestBibleChunk:
    def test_chunk_creation(self):
        c = BibleChunk(
            id="bibbia_gen_1_1_31",
            text="testo",
            metadata={"source": "Bible", "book": "Genesi", "chapter": 1}
        )
        assert c.id == "bibbia_gen_1_1_31"
        assert c.metadata["source"] == "Bible"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/homily-agent && pip install pytest && pytest tests/rag/test_bible_parser.py -v
```

Expected: ModuleNotFoundError / ImportError

- [ ] **Step 3: Write minimal Verse, BibleChunk and BookMetadata definitions**

```python
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


BOOK_TO_ABBREVIATION: dict[str, str] = {
    "Genesi": "Gen", "Esodo": "Es", "Levitico": "Lv", "Numeri": "Nm",
    "Deuteronomio": "Dt", "Giosuè": "Gs", "Giudici": "Gdc", "Rut": "Rt",
    "1 Samuele": "1Sam", "2 Samuele": "2Sam", "1 Re": "1Re", "2 Re": "2Re",
    "1 Cronache": "1Cr", "2 Cronache": "2Cr", "Esdra": "Esd", "Neemia": "Ne",
    "Tobia": "Tb", "Giuditta": "Gdt", "Ester": "Est",
    "1 Maccabei": "1Mac", "2 Maccabei": "2Mac", "Giobbe": "Gb",
    "Salmi": "Sal", "Proverbi": "Pr", "Qoèlet": "Qo",
    "Cantico dei Cantici": "Ct", "Sapienza": "Sap", "Siracide": "Sir",
    "Isaia": "Is", "Geremia": "Ger", "Lamentazioni": "Lam", "Baruc": "Bar",
    "Ezechiele": "Ez", "Daniele": "Dn", "Osea": "Os", "Gioele": "Gl",
    "Amos": "Am", "Abdia": "Abd", "Giona": "Gn", "Michea": "Mi",
    "Naum": "Na", "Abacuc": "Ab", "Sofonia": "Sof", "Aggeo": "Ag",
    "Zaccaria": "Zc", "Malachia": "Ml",
    "Matteo": "Mt", "Marco": "Mc", "Luca": "Lc", "Giovanni": "Gv",
    "Atti degli Apostoli": "At", "Romani": "Rm",
    "1 Corinzi": "1Cor", "2 Corinzi": "2Cor", "Galati": "Gal",
    "Efesini": "Ef", "Filippesi": "Fil", "Colossesi": "Col",
    "1 Tessalonicesi": "1Ts", "2 Tessalonicesi": "2Ts",
    "1 Timoteo": "1Tm", "2 Timoteo": "2Tm", "Tito": "Tt", "Filemone": "Fm",
    "Ebrei": "Eb", "Giacomo": "Gc", "1 Pietro": "1Pt", "2 Pietro": "2Pt",
    "1 Giovanni": "1Gv", "2 Giovanni": "2Gv", "3 Giovanni": "3Gv",
    "Giuda": "Gd", "Apocalisse": "Ap",
}

BOOK_TO_SECTION: dict[str, str] = {
    "Genesi": "Pentateuco", "Esodo": "Pentateuco",
    "Levitico": "Pentateuco", "Numeri": "Pentateuco",
    "Deuteronomio": "Pentateuco",
    "Giosuè": "Storici", "Giudici": "Storici", "Rut": "Storici",
    "1 Samuele": "Storici", "2 Samuele": "Storici",
    "1 Re": "Storici", "2 Re": "Storici",
    "1 Cronache": "Storici", "2 Cronache": "Storici",
    "Esdra": "Storici", "Neemia": "Storici", "Tobia": "Storici",
    "Giuditta": "Storici", "Ester": "Storici",
    "1 Maccabei": "Storici", "2 Maccabei": "Storici",
    "Giobbe": "Poetici", "Salmi": "Poetici", "Proverbi": "Poetici",
    "Qoèlet": "Poetici", "Cantico dei Cantici": "Poetici",
    "Sapienza": "Poetici", "Siracide": "Poetici",
    "Isaia": "Profeti", "Geremia": "Profeti", "Lamentazioni": "Profeti",
    "Baruc": "Profeti", "Ezechiele": "Profeti", "Daniele": "Profeti",
    "Osea": "Profeti minori", "Gioele": "Profeti minori",
    "Amos": "Profeti minori", "Abdia": "Profeti minori",
    "Giona": "Profeti minori", "Michea": "Profeti minori",
    "Naum": "Profeti minori", "Abacuc": "Profeti minori",
    "Sofonia": "Profeti minori", "Aggeo": "Profeti minori",
    "Zaccaria": "Profeti minori", "Malachia": "Profeti minori",
    "Matteo": "Vangeli", "Marco": "Vangeli", "Luca": "Vangeli",
    "Giovanni": "Vangeli", "Atti degli Apostoli": "Storici",
    "Romani": "Lettere Paolo", "1 Corinzi": "Lettere Paolo",
    "2 Corinzi": "Lettere Paolo", "Galati": "Lettere Paolo",
    "Efesini": "Lettere Paolo", "Filippesi": "Lettere Paolo",
    "Colossesi": "Lettere Paolo", "1 Tessalonicesi": "Lettere Paolo",
    "2 Tessalonicesi": "Lettere Paolo", "1 Timoteo": "Lettere Paolo",
    "2 Timoteo": "Lettere Paolo", "Tito": "Lettere Paolo",
    "Filemone": "Lettere Paolo", "Ebrei": "Lettere Paolo",
    "Giacomo": "Lettere cattoliche", "1 Pietro": "Lettere cattoliche",
    "2 Pietro": "Lettere cattoliche", "1 Giovanni": "Lettere cattoliche",
    "2 Giovanni": "Lettere cattoliche", "3 Giovanni": "Lettere cattoliche",
    "Giuda": "Lettere cattoliche", "Apocalisse": "Apocalisse",
}

BOOK_TO_TESTAMENT: dict[str, str] = {
    "Genesi": "AT", "Esodo": "AT", "Levitico": "AT", "Numeri": "AT",
    "Deuteronomio": "AT", "Giosuè": "AT", "Giudici": "AT", "Rut": "AT",
    "1 Samuele": "AT", "2 Samuele": "AT", "1 Re": "AT", "2 Re": "AT",
    "1 Cronache": "AT", "2 Cronache": "AT", "Esdra": "AT", "Neemia": "AT",
    "Tobia": "AT", "Giuditta": "AT", "Ester": "AT",
    "1 Maccabei": "AT", "2 Maccabei": "AT", "Giobbe": "AT",
    "Salmi": "AT", "Proverbi": "AT", "Qoèlet": "AT",
    "Cantico dei Cantici": "AT", "Sapienza": "AT", "Siracide": "AT",
    "Isaia": "AT", "Geremia": "AT", "Lamentazioni": "AT", "Baruc": "AT",
    "Ezechiele": "AT", "Daniele": "AT", "Osea": "AT", "Gioele": "AT",
    "Amos": "AT", "Abdia": "AT", "Giona": "AT", "Michea": "AT",
    "Naum": "AT", "Abacuc": "AT", "Sofonia": "AT", "Aggeo": "AT",
    "Zaccaria": "AT", "Malachia": "AT",
    "Matteo": "NT", "Marco": "NT", "Luca": "NT", "Giovanni": "NT",
    "Atti degli Apostoli": "NT",
    "Romani": "NT", "1 Corinzi": "NT", "2 Corinzi": "NT",
    "Galati": "NT", "Efesini": "NT", "Filippesi": "NT",
    "Colossesi": "NT", "1 Tessalonicesi": "NT", "2 Tessalonicesi": "NT",
    "1 Timoteo": "NT", "2 Timoteo": "NT", "Tito": "NT", "Filemone": "NT",
    "Ebrei": "NT", "Giacomo": "NT", "1 Pietro": "NT", "2 Pietro": "NT",
    "1 Giovanni": "NT", "2 Giovanni": "NT", "3 Giovanni": "NT",
    "Giuda": "NT", "Apocalisse": "NT",
}

BOOK_TO_TYPE: dict[str, str] = {
    "Genesi": "narrative", "Esodo": "narrative", "Levitico": "law",
    "Numeri": "narrative", "Deuteronomio": "law",
    "Giosuè": "narrative", "Giudici": "narrative", "Rut": "narrative",
    "1 Samuele": "narrative", "2 Samuele": "narrative",
    "1 Re": "narrative", "2 Re": "narrative",
    "1 Cronache": "narrative", "2 Cronache": "narrative",
    "Esdra": "narrative", "Neemia": "narrative", "Tobia": "narrative",
    "Giuditta": "narrative", "Ester": "narrative",
    "1 Maccabei": "narrative", "2 Maccabei": "narrative",
    "Giobbe": "poetry", "Salmi": "poetry", "Proverbi": "poetry",
    "Qoèlet": "poetry", "Cantico dei Cantici": "poetry",
    "Sapienza": "poetry", "Siracide": "poetry",
    "Isaia": "prophecy", "Geremia": "prophecy", "Lamentazioni": "poetry",
    "Baruc": "prophecy", "Ezechiele": "prophecy", "Daniele": "prophecy",
    "Osea": "prophecy", "Gioele": "prophecy", "Amos": "prophecy",
    "Abdia": "prophecy", "Giona": "narrative", "Michea": "prophecy",
    "Naum": "prophecy", "Abacuc": "prophecy", "Sofonia": "prophecy",
    "Aggeo": "prophecy", "Zaccaria": "prophecy", "Malachia": "prophecy",
    "Matteo": "gospel", "Marco": "gospel", "Luca": "gospel",
    "Giovanni": "gospel", "Atti degli Apostoli": "narrative",
    "Romani": "letter", "1 Corinzi": "letter", "2 Corinzi": "letter",
    "Galati": "letter", "Efesini": "letter", "Filippesi": "letter",
    "Colossesi": "letter", "1 Tessalonicesi": "letter",
    "2 Tessalonicesi": "letter", "1 Timoteo": "letter",
    "2 Timoteo": "letter", "Tito": "letter", "Filemone": "letter",
    "Ebrei": "letter", "Giacomo": "letter", "1 Pietro": "letter",
    "2 Pietro": "letter", "1 Giovanni": "letter", "2 Giovanni": "letter",
    "3 Giovanni": "letter", "Giuda": "letter", "Apocalisse": "prophecy",
}


class BibleParser:
    def __init__(self, html_dir: str):
        self.html_dir = Path(html_dir)

    def parse_all(self) -> list[Verse]:
        verses: list[Verse] = []
        for path in sorted(self.html_dir.glob("*.htm")):
            verses.extend(self.parse_file(path))
        return verses

    def parse_file(self, path: Path) -> list[Verse]:
        from bs4 import BeautifulSoup
        html = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        book = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""
        abbreviation = BOOK_TO_ABBREVIATION.get(book, "")
        testament = BOOK_TO_TESTAMENT.get(book, "")
        section = BOOK_TO_SECTION.get(book, "")
        book_type = BOOK_TO_TYPE.get(book, "")

        verses: list[Verse] = []
        for a_tag in soup.find_all("a", href=lambda h: h and h.startswith("#cap_")):
            chapter_anchor = a_tag.get("name", "")
            chapter = self._chapter_from_anchor(chapter_anchor)
            chapter_verses = self._extract_chapter_verses(soup, chapter_anchor, chapter)
            for v in chapter_verses:
                verses.append(Verse(
                    book=book, abbreviation=abbreviation, chapter=v["chapter"],
                    verse=v["verse"], text=v["text"],
                    testament=testament, section=section, book_type=book_type,
                ))
        return verses

    @staticmethod
    def _chapter_from_anchor(anchor: str) -> int:
        parts = anchor.split("_")
        for p in parts:
            if p.isdigit():
                return int(p)
        return 0

    @staticmethod
    def _extract_chapter_verses(soup, chapter_anchor: str, chapter: int) -> list[dict]:
        h2 = soup.find("a", attrs={"name": chapter_anchor})
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
                    plain = BeautifulSoup(texts[i + 1] if i + 1 < len(texts) else "", "html.parser").get_text(" ", strip=True)
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

    def _join_verses(self, verses: list[Verse]) -> str:
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
        i = 0
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
```

- [ ] **Step 4: Run tests again**

```bash
cd packages/homily-agent && pytest tests/rag/test_bible_parser.py -v
```

Expected: PASS

- [ ] **Step 5: Write test for parsing a real HTML file**

```python
class TestBibleParser:
    def test_parse_genesi_creates_verses(self):
        from pathlib import Path
        parser = BibleParser("tests/rag/fixtures")
        # Create minimal fixture inline: at01-genesi.htm with Gen 1,1-5
        fixture_dir = Path("tests/rag/fixtures")
        fixture_dir.mkdir(parents=True, exist_ok=True)
        html = """<!DOCTYPE html><html><body>
<h1>Genesi</h1>
<ul><li><a href="#cap_genesi_1" name="capind_genesi_1">CAPITOLO 1</a></li></ul>
<hr>
<h2><a href="#capind_genesi_1" name="cap_genesi_1"><i>GENESI - 1</i></a></h2>
<p><sup><b>1</b></sup>In principio Dio creò il cielo e la terra.
<sup><b>2</b></sup>La terra era informe e deserta.</p>
</body></html>"""
        (fixture_dir / "at01-genesi.htm").write_text(html, encoding="utf-8")

        verses = parser.parse_all()
        assert len(verses) == 2
        assert verses[0].book == "Genesi"
        assert verses[0].abbreviation == "Gen"
        assert verses[0].chapter == 1
        assert verses[0].verse == 1
        assert "In principio" in verses[0].text
        assert verses[0].testament == "AT"
        assert verses[0].section == "Pentateuco"
        assert verses[0].book_type == "narrative"

        # Cleanup
        import shutil
        shutil.rmtree("tests/rag/fixtures", ignore_errors=True)

    def test_parse_file_returns_verses_sorted(self):
        from pathlib import Path
        fixture_dir = Path("tests/rag/fixtures")
        fixture_dir.mkdir(parents=True, exist_ok=True)
        html = """<!DOCTYPE html><html><body>
<h1>Abdia</h1>
<ul><li><a href="#cap_abdia_1" name="capind_abdia_1">CAPITOLO 1</a></li></ul>
<hr>
<h2><a href="#capind_abdia_1" name="cap_abdia_1"><i>ABDIA - 1</i></a></h2>
<p><sup><b>1</b></sup>Visione di Abdia.
<sup><b>2</b></sup>Ecco, ti ho reso piccolo tra i popoli.</p>
</body></html>"""
        (fixture_dir / "at38-libro_del_profeta_abdia.htm").write_text(html, encoding="utf-8")

        parser = BibleParser("tests/rag/fixtures")
        verses = parser.parse_all()
        assert len(verses) == 2
        assert verses[0].abbreviation == "Abd"
        assert verses[0].testament == "AT"
        assert verses[0].section == "Profeti minori"
        assert verses[0].book_type == "prophecy"

        import shutil
        shutil.rmtree("tests/rag/fixtures", ignore_errors=True)
```

- [ ] **Step 6: Run tests**

```bash
cd packages/homily-agent && pytest tests/rag/test_bible_parser.py -v
```

Expected: PASS

- [ ] **Step 7: Write test for Chunker**

```python
class TestChunker:
    def test_short_chapter_is_one_chunk(self):
        verses = [
            Verse("Abdia", "Abd", 1, 1, "Visione.", "AT", "Profeti minori", "prophecy"),
            Verse("Abdia", "Abd", 1, 2, "Ecco ti ho reso piccolo.", "AT", "Profeti minori", "prophecy"),
        ]
        chunker = Chunker()
        chunks = chunker.chunk_verses(verses)
        assert len(chunks) == 1
        assert chunks[0].metadata["chapter"] == 1
        assert chunks[0].metadata["verse_start"] == 1
        assert chunks[0].metadata["verse_end"] == 2

    def test_long_chapter_is_sub_chunked(self):
        verses = [
            Verse("Salmi", "Sal", 119, i, f"Versetto {i}.", "AT", "Poetici", "poetry")
            for i in range(1, 180)
        ]
        chunker = Chunker()
        chunks = chunker.chunk_verses(verses)
        assert len(chunks) > 1
        assert all(c.metadata["chapter"] == 119 for c in chunks)
        assert chunks[0].metadata["verse_start"] == 1
        assert chunks[-1].metadata["verse_end"] == 176

    def test_metadata_includes_all_fields(self):
        verses = [
            Verse("Genesi", "Gen", 1, 1, "In principio.", "AT", "Pentateuco", "narrative"),
        ]
        chunker = Chunker()
        chunks = chunker.chunk_verses(verses)
        meta = chunks[0].metadata
        assert meta["source"] == "Bible"
        assert meta["book"] == "Genesi"
        assert meta["abbreviation"] == "Gen"
        assert meta["chapter"] == 1
        assert meta["verse_start"] == 1
        assert meta["verse_end"] == 1
        assert meta["testament"] == "AT"
        assert meta["section"] == "Pentateuco"
        assert meta["book_type"] == "narrative"
```

- [ ] **Step 8: Run all Bible parser tests**

```bash
cd packages/homily-agent && pytest tests/rag/test_bible_parser.py -v
```

Expected: ALL PASS (5 tests)

- [ ] **Step 9: Install deps and add to pyproject.toml**

```bash
cd packages/homily-agent && uv add --optional ml beautifulsoup4 lxml
```

Add to pyproject.toml `[project.optional-dependencies] ml`:
```
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
```

---

### Task 3: Create Catechism Parser

**Files:**
- Create: `packages/homily-agent/src/homily_agent/rag/catechism_parser.py`
- Create: `packages/homily-agent/tests/rag/test_catechism_parser.py`

- [ ] **Step 1: Write test for CatechismParser**

```python
import pytest
from homily_agent.rag.catechism_parser import Paragraph, CatechismParser


class TestCatechismParser:
    def test_paragraph_creation(self):
        p = Paragraph(
            part=1, part_title="La professione della fede",
            section=1, section_title="Io credo",
            chapter=1, chapter_title="L'uomo è capace di Dio",
            subsection="I", subsection_title="La vita dell'uomo",
            paragraph_num=1,
            paragraph_title="",
            text="Dio, infinitamente perfetto e beato in se stesso..."
        )
        assert p.part == 1
        assert p.paragraph_num == 1

    def test_parse_pdf_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            CatechismParser("tests/rag/fixtures/nonexistent.pdf")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/homily-agent && pytest tests/rag/test_catechism_parser.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: Install PyMuPDF**

```bash
cd packages/homily-agent && uv add --optional ml pymupdf
```

Add to pyproject.toml:
```
    "pymupdf>=1.24.0",
```

- [ ] **Step 4: Write CatechismParser implementation**

```python
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import fitz
except ImportError:
    fitz = None


@dataclass
class Paragraph:
    part: int
    part_title: str
    section: int
    section_title: str
    chapter: int
    chapter_title: str
    subsection: str
    subsection_title: str
    paragraph_num: int
    paragraph_title: str
    text: str


PARTE_PATTERN = re.compile(r'^PARTE\s+(PRIMA|SECONDA|TERZA|QUARTA)\s*[-–]\s*(.+)$')
SEZIONE_PATTERN = re.compile(r'^SEZIONE\s+(PRIMA|SECONDA|TERZA)\s*[-–]\s*(.+)$')
CAPITOLO_PATTERN = re.compile(r'^CAPITOLO\s+(PRIMO|SECONDO|TERZO|QUARTO|QUINTO|SESTO|SETTIMO|OTTAVO|NONO|DECIMO)\s*[-–]\s*(.+)$')
PARA_PATTERN = re.compile(r'^\s*(\d{1,4})\s+(.+)$')

ROMAN_TO_INT = {
    "PRIMA": 1, "PRIMO": 1,
    "SECONDA": 2, "SECONDO": 2,
    "TERZA": 3, "TERZO": 3,
    "QUARTA": 4, "QUARTO": 4,
    "QUINTA": 5, "QUINTO": 5,
    "SESTA": 6, "SESTO": 6,
    "SETTIMO": 7,
    "OTTAVO": 8,
    "NONO": 9,
    "DECIMO": 10,
}

SUBSECTION_PATTERN = re.compile(r'^([IVXLCD]+)\.\s+(.+)$')


class CatechismParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"CCC PDF not found: {pdf_path}")
        if fitz is None:
            raise ImportError("pymupdf is required. Install with: pip install pymupdf")

    def parse(self) -> list[Paragraph]:
        doc = fitz.open(str(self.pdf_path))
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()
        return self._extract_paragraphs(full_text)

    def _extract_paragraphs(self, text: str) -> list[Paragraph]:
        lines = text.split("\n")
        current_part = current_part_title = 0
        current_section = current_section_title = 0
        current_chapter = current_chapter_title = 0
        current_subsection = ""
        current_subsection_title = ""

        paragraphs: list[Paragraph] = []
        buf: list[str] = []

        def flush_para(num: int, title: str) -> None:
            text_body = " ".join(buf).strip()
            if text_body:
                paragraphs.append(Paragraph(
                    part=current_part,
                    part_title=current_part_title,
                    section=current_section,
                    section_title=current_section_title,
                    chapter=current_chapter,
                    chapter_title=current_chapter_title,
                    subsection=current_subsection,
                    subsection_title=current_subsection_title,
                    paragraph_num=num,
                    paragraph_title=title,
                    text=text_body,
                ))
            buf.clear()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            parte_m = PARTE_PATTERN.match(stripped)
            if parte_m:
                current_part = ROMAN_TO_INT.get(parte_m.group(1), 0)
                current_part_title = parte_m.group(2).strip().strip('"').strip('"')
                continue

            sez_m = SEZIONE_PATTERN.match(stripped)
            if sez_m:
                current_section = ROMAN_TO_INT.get(sez_m.group(1), 0)
                current_section_title = sez_m.group(2).strip().strip('"').strip('"')
                current_subsection = ""
                current_subsection_title = ""
                continue

            cap_m = CAPITOLO_PATTERN.match(stripped)
            if cap_m:
                current_chapter = ROMAN_TO_INT.get(cap_m.group(1), 0)
                current_chapter_title = cap_m.group(2).strip().strip('"').strip('"')
                current_subsection = ""
                current_subsection_title = ""
                continue

            sub_m = SUBSECTION_PATTERN.match(stripped)
            if sub_m:
                current_subsection = sub_m.group(1)
                current_subsection_title = sub_m.group(2).strip()
                continue

            para_m = PARA_PATTERN.match(stripped)
            if para_m and 1 <= int(para_m.group(1)) <= 2865:
                flush_para(
                    int(para_m.group(1)),
                    ""  # CCC paragraphs don't have per-para titles
                )
                buf.append(para_m.group(2))
            else:
                buf.append(stripped)

        flush_para(0, "")
        return paragraphs
```

- [ ] **Step 5: Run tests**

```bash
cd packages/homily-agent && pytest tests/rag/test_catechism_parser.py -v
```

Expected: PASS

---

### Task 4: Update RAG `__init__.py`

**Files:**
- Modify: `packages/homily-agent/src/homily_agent/rag/__init__.py`

- [ ] **Step 1: Add new exports**

```python
from .embeddings import EmbeddingService
from .retrieval import RetrievalService, load_theological_corpus
from .bible_parser import BibleParser, Chunker, Verse, BibleChunk
from .catechism_parser import CatechismParser, Paragraph

__all__ = [
    "EmbeddingService", "RetrievalService", "load_theological_corpus",
    "BibleParser", "Chunker", "Verse", "BibleChunk",
    "CatechismParser", "Paragraph",
]
```

---

### Task 5: Create Ingestion CLI Script

**Files:**
- Create: `packages/homily-agent/scripts/ingest_corpus.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""
Ingest Bibbia CEI 2008 and Catechismo della Chiesa Cattolica into ChromaDB corpus.
"""

import argparse
import logging
from pathlib import Path

from homily_agent.rag import RetrievalService, BibleParser, Chunker, CatechismParser

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BIBLE_HTML_DIR = Path(__file__).resolve().parent.parent.parent.parent / "support" / "bibbia2008" / "bcei2008"
CCC_PDF_PATH = Path(__file__).resolve().parent.parent.parent.parent / "support" / "catechismo" / "catechismo-della-chiesa-cattolica.pdf"


def main():
    parser = argparse.ArgumentParser(description="Ingest theological sources into ChromaDB corpus")
    parser.add_argument("--reset", action="store_true", help="Reset the collection before ingesting")
    parser.add_argument("--bible-dir", type=str, default=str(BIBLE_HTML_DIR))
    parser.add_argument("--ccc-path", type=str, default=str(CCC_PDF_PATH))
    args = parser.parse_args()

    retrieval = RetrievalService()

    if args.reset:
        retrieval.reset_collection()
        logger.info("Collection reset")

    # Bible
    logger.info("Parsing Bible CEI 2008...")
    bible_parser = BibleParser(args.bible_dir)
    verses = bible_parser.parse_all()
    logger.info(f"Parsed {len(verses)} verses")

    chunker = Chunker()
    bible_chunks = chunker.chunk_verses(verses)
    logger.info(f"Created {len(bible_chunks)} Bible chunks")

    retrieval.add_documents(
        documents=[c.text for c in bible_chunks],
        ids=[c.id for c in bible_chunks],
        metadatas=[c.metadata for c in bible_chunks],
    )
    logger.info(f"Ingested {len(bible_chunks)} Bible chunks")

    # CCC
    logger.info("Parsing Catechismo...")
    ccc_parser = CatechismParser(args.ccc_path)
    paragraphs = ccc_parser.parse()
    logger.info(f"Parsed {len(paragraphs)} CCC paragraphs")

    ccc_docs = []
    ccc_ids = []
    ccc_metas = []
    for p in paragraphs:
        para_id = f"ccc_{p.paragraph_num}"
        ccc_docs.append(p.text)
        ccc_ids.append(para_id)
        ccc_metas.append({
            "source": "CCC",
            "part": p.part,
            "part_title": p.part_title,
            "section": p.section,
            "section_title": p.section_title,
            "chapter": p.chapter,
            "chapter_title": p.chapter_title,
            "subsection": p.subsection,
            "subsection_title": p.subsection_title,
            "paragraph_num": p.paragraph_num,
            "paragraph_title": p.paragraph_title,
        })

    retrieval.add_documents(documents=ccc_docs, ids=ccc_ids, metadatas=ccc_metas)
    logger.info(f"Ingested {len(ccc_docs)} CCC paragraphs")

    total = retrieval.get_document_count()
    logger.info(f"Total documents in corpus: {total}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the script runs**

```bash
cd packages/homily-agent && python scripts/ingest_corpus.py --reset
```

---

### Task 6: Integration — Verify Retrieval

- [ ] **Step 1: Integration test**

Create `packages/homily-agent/tests/rag/test_integration_corpus.py`:

```python
import pytest
from homily_agent.rag import RetrievalService


class TestCorpusRetrieval:
    @pytest.fixture
    def retrieval(self):
        svc = RetrievalService()
        svc._ensure_initialized()
        if svc.get_document_count() == 0:
            pytest.skip("No documents in corpus, run ingest_corpus.py first")
        return svc

    def test_retrieve_by_theme(self, retrieval):
        results = retrieval.retrieve("beatitudini Regno dei cieli")
        assert len(results) > 0
        assert any("Bible" in r.source for r in results)

    def test_retrieve_ccc(self, retrieval):
        results = retrieval.retrieve("desiderio di Dio")
        assert len(results) > 0
        assert any(r.metadata.get("source") == "CCC" for r in results)
```

```bash
cd packages/homily-agent && pytest tests/rag/test_integration_corpus.py -v
```

---

### Task 7: Commit

- [ ] **Step 1: Stage and commit**

```bash
git add packages/homily-agent/src/homily_agent/rag/bible_parser.py
git add packages/homily-agent/src/homily_agent/rag/catechism_parser.py
git add packages/homily-agent/src/homily_agent/rag/__init__.py
git add packages/homily-agent/src/homily_agent/rag/retrieval.py
git add packages/homily-agent/scripts/ingest_corpus.py
git add packages/homily-agent/tests/rag/
git add packages/homily-agent/pyproject.toml
git add docs/superpowers/plans/2026-05-18-bible-knowledge-base.md
git commit -m "feat: ingest Bibbia CEI 2008 and CCC into ChromaDB corpus
- Add BibleParser for 73 HTML files (CEI 2008)
- Add CatechismParser for CCC PDF (517 pages)
- Add Chunker with chapter-level + sub-chunking strategy
- Update RetrievalService defaults (corpus collection, data/ path)
- Add reset_collection method
- Add ingestion CLI script
- Include tests with real HTML fixture"
```
