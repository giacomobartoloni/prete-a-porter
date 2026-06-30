import pytest
from pathlib import Path
from homily_agent.rag.bible_parser import Verse, BibleChunk, BibleParser, Chunker, BeautifulSoup


class TestVerse:
    def test_verse_creation(self):
        v = Verse(
            book="Genesi", abbreviation="Gen", chapter=1, verse=1,
            text="In principio Dio creò il cielo e la terra.",
            testament="AT", section="Pentateuco", book_type="narrative",
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
            metadata={"source": "Bible", "book": "Genesi", "chapter": 1},
        )
        assert c.id == "bibbia_gen_1_1_31"
        assert c.metadata["source"] == "Bible"


@pytest.mark.skipif(
    BeautifulSoup is None,
    reason="beautifulsoup4 not installed (optional [ml] dependency)",
)
class TestBibleParser:
    def test_parse_genesi_creates_verses(self):
        fixture_dir = Path("tests/rag/fixtures")
        fixture_dir.mkdir(parents=True, exist_ok=True)
        html = """<!DOCTYPE html><html><body>
<h1>GENESI</h1>
<ul><li><a href="#cap_genesi_1" name="capind_genesi_1">CAPITOLO 1</a></li></ul>
<hr>
<h2><a href="#capind_genesi_1" name="cap_genesi_1"><i>GENESI - 1</i></a></h2>
<p><sup><b>1</b></sup>In principio Dio creò il cielo e la terra.
<sup><b>2</b></sup>La terra era informe e deserta.</p>
</body></html>"""
        (fixture_dir / "at01-genesi.htm").write_text(html, encoding="utf-8")

        try:
            parser = BibleParser("tests/rag/fixtures")
            verses = parser.parse_all()
            assert len(verses) == 2
            assert verses[0].book == "GENESI"
            assert verses[0].abbreviation == "Gen"
            assert verses[0].chapter == 1
            assert verses[0].verse == 1
            assert "In principio" in verses[0].text
            assert verses[0].testament == "AT"
            assert verses[0].section == "Pentateuco"
            assert verses[0].book_type == "narrative"
        finally:
            import shutil
            shutil.rmtree("tests/rag/fixtures", ignore_errors=True)

    def test_parse_file_abdia(self):
        fixture_dir = Path("tests/rag/fixtures")
        fixture_dir.mkdir(parents=True, exist_ok=True)
        html = """<!DOCTYPE html><html><body>
<h1>LIBRO DEL PROFETA ABDIA</h1>
<ul><li><a href="#cap_abdia_1" name="capind_abdia_1">CAPITOLO 1</a></li></ul>
<hr>
<h2><a href="#capind_abdia_1" name="cap_abdia_1"><i>ABDIA - 1</i></a></h2>
<p><sup><b>1</b></sup>Visione di Abdia.
<sup><b>2</b></sup>Ecco, ti ho reso piccolo tra i popoli.</p>
</body></html>"""
        (fixture_dir / "at38-libro_del_profeta_abdia.htm").write_text(html, encoding="utf-8")

        try:
            parser = BibleParser("tests/rag/fixtures")
            verses = parser.parse_all()
            assert len(verses) == 2
            assert verses[0].abbreviation == "Abd"
            assert verses[0].testament == "AT"
            assert verses[0].section == "Profeti minori"
            assert verses[0].book_type == "prophecy"
        finally:
            import shutil
            shutil.rmtree("tests/rag/fixtures", ignore_errors=True)


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
            Verse("Salmi", "Sal", 119, i, f"Versetto {i}.", "AT", "Poetici e Sapienziali", "poetry")
            for i in range(1, 180)
        ]
        chunker = Chunker()
        chunks = chunker.chunk_verses(verses)
        assert len(chunks) > 1
        assert all(c.metadata["chapter"] == 119 for c in chunks)
        assert chunks[0].metadata["verse_start"] == 1
        assert chunks[-1].metadata["verse_end"] == 179

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
