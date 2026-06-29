import re
import logging
from dataclasses import dataclass
from pathlib import Path

FITZ_AVAILABLE = False

logger = logging.getLogger(__name__)


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
SEZIONE_PATTERN = re.compile(r'^SEZIONE\s+(PRIMA|SECONDA|TERZA)\s*[-–]\s*["]?(.+?)["]?\s*$')
CAPITOLO_PATTERN = re.compile(
    r'^CAPITOLO\s+(PRIMO|SECONDO|TERZO|QUARTO|QUINTO|SESTO|SETTIMO|OTTAVO|NONO|DECIMO)\s*[-–]\s*(.+)$'
)
PARA_PATTERN = re.compile(r'^\s*(\d{1,4})(?:\s|$)(.+)$')
SUBSECTION_PATTERN = re.compile(r'^([IVXLCD]+)\.\s+(.+)$')

ROMAN_TO_INT = {
    "PRIMA": 1, "PRIMO": 1,
    "SECONDA": 2, "SECONDO": 2,
    "TERZA": 3, "TERZO": 3,
    "QUARTA": 4, "QUARTO": 4,
    "QUINTA": 5, "QUINTO": 5,
    "SESTA": 6, "SESTO": 6,
    "SETTIMA": 7, "SETTIMO": 7,
    "OTTAVA": 8, "OTTAVO": 8,
    "NONA": 9, "NONO": 9,
    "DECIMA": 10, "DECIMO": 10,
}


class CatechismParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"CCC PDF not found: {pdf_path}")

    def parse(self) -> list[Paragraph]:
        try:
            import fitz
        except ImportError:
            raise ImportError("pymupdf is required. Install with: pip install pymupdf")
        doc = fitz.open(str(self.pdf_path))
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()
        return self._extract_paragraphs(full_text)

    def _extract_paragraphs(self, text: str) -> list[Paragraph]:
        lines = text.split("\n")
        current_part = 0
        current_part_title = ""
        current_section = 0
        current_section_title = ""
        current_chapter = 0
        current_chapter_title = ""
        current_subsection = ""
        current_subsection_title = ""

        paragraphs: list[Paragraph] = []
        buf: list[str] = []
        last_para_num = 0

        def flush_para() -> None:
            nonlocal last_para_num
            text_body = " ".join(buf).strip()
            if text_body and last_para_num > 0:
                paragraphs.append(Paragraph(
                    part=current_part,
                    part_title=current_part_title,
                    section=current_section,
                    section_title=current_section_title,
                    chapter=current_chapter,
                    chapter_title=current_chapter_title,
                    subsection=current_subsection,
                    subsection_title=current_subsection_title,
                    paragraph_num=last_para_num,
                    paragraph_title="",
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
                current_part_title = parte_m.group(2).strip('" ')
                continue

            sez_m = SEZIONE_PATTERN.match(stripped)
            if sez_m:
                current_section = ROMAN_TO_INT.get(sez_m.group(1), 0)
                current_section_title = sez_m.group(2).strip('" ')
                current_subsection = ""
                current_subsection_title = ""
                continue

            cap_m = CAPITOLO_PATTERN.match(stripped)
            if cap_m:
                current_chapter = ROMAN_TO_INT.get(cap_m.group(1), 0)
                current_chapter_title = cap_m.group(2).strip('" ')
                current_subsection = ""
                current_subsection_title = ""
                continue

            sub_m = SUBSECTION_PATTERN.match(stripped)
            if sub_m:
                current_subsection = sub_m.group(1)
                current_subsection_title = sub_m.group(2).strip()
                continue

            para_m = PARA_PATTERN.match(stripped)
            if para_m:
                num = int(para_m.group(1))
                if 1 <= num <= 2865:
                    flush_para()
                    last_para_num = num
                    buf.append(para_m.group(2))
                    continue

            buf.append(stripped)

        flush_para()
        return paragraphs
