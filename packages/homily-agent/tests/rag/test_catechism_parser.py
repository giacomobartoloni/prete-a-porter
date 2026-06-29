import pytest
from homily_agent.rag.catechism_parser import Paragraph, CatechismParser


class TestParagraph:
    def test_paragraph_creation(self):
        p = Paragraph(
            part=1, part_title="La professione della fede",
            section=1, section_title="Io credo",
            chapter=1, chapter_title="L'uomo è capace di Dio",
            subsection="I", subsection_title="La vita dell'uomo",
            paragraph_num=1,
            paragraph_title="",
            text="Dio, infinitamente perfetto e beato in se stesso...",
        )
        assert p.part == 1
        assert p.paragraph_num == 1

    def test_parse_pdf_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            CatechismParser("tests/rag/fixtures/nonexistent.pdf")


class TestCatechismParser:
    def test_extract_paragraphs_from_text(self):
        text = """
PARTE PRIMA - LA PROFESSIONE DELLA FEDE
SEZIONE PRIMA - IO CREDO
CAPITOLO PRIMO - L'UOMO E' CAPACE DI DIO
I. La vita dell'uomo
1 Dio, infinitamente perfetto e beato in se stesso.
2 Affinché questo appello risuonasse per tutta la terra.
        """
        parser = CatechismParser.__new__(CatechismParser)
        # skip __init__ to avoid file check
        result = parser._extract_paragraphs(text)
        assert len(result) == 2
        assert result[0].paragraph_num == 1
        assert result[0].part == 1
        assert result[0].section == 1
        assert result[0].chapter == 1
        assert result[0].subsection == "I"
        assert "Dio" in result[0].text
        assert result[1].paragraph_num == 2

    def test_extract_ignores_non_canonical_numbers(self):
        text = """
PARTE PRIMA - LA PROFESSIONE DELLA FEDE
10000 Not a real CCC paragraph.
        """
        parser = CatechismParser.__new__(CatechismParser)
        result = parser._extract_paragraphs(text)
        assert len(result) == 0
