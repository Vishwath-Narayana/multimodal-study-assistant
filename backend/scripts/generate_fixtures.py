"""Generates the synthetic ingestion test fixtures under tests/fixtures/.

These are small, deterministic, synthetic "study notes" documents (title,
headings, paragraphs, a list, a table, an image) built programmatically so
we never commit copyrighted student material — see
docs/architecture/ingestion.md and PHASE 1 §18 of the project brief.

Regenerate with:

    uv run python scripts/generate_fixtures.py

The generated files are committed to the repo (they are a few KB each) so
tests don't need to regenerate them, and so accidental content drift is
visible in `git diff`.
"""

from __future__ import annotations

import base64
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# A minimal valid 1x1 transparent PNG, embedded directly so fixture
# generation has no binary asset dependency of its own.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

TITLE = "Cell Biology Study Notes"
H1 = "Chapter 1: Cell Biology"
H2_A = "Section 1.1: Photosynthesis"
H2_B = "Section 1.2: Cellular Respiration"
PARA_A = (
    "Photosynthesis converts light energy into chemical energy stored in "
    "glucose. It occurs in the chloroplasts of plant cells and consists of "
    "the light-dependent reactions and the Calvin cycle."
)
PARA_A2 = "Key steps in the light-dependent reactions:"
LIST_A = ["Light absorption by chlorophyll", "Electron transport chain", "ATP and NADPH synthesis"]
TABLE_HEADER = ["Organelle", "Function"]
TABLE_ROWS = [["Mitochondria", "ATP production"], ["Chloroplast", "Photosynthesis"]]
PARA_B = (
    "Cellular respiration releases energy stored in glucose through "
    "glycolysis, the citric acid cycle, and oxidative phosphorylation."
)


def _tiny_png_path(tmp_dir: Path) -> Path:
    path = tmp_dir / "_tiny.png"
    path.write_bytes(_TINY_PNG)
    return path


def generate_html() -> None:
    image_data_uri = "data:image/png;base64," + base64.b64encode(_TINY_PNG).decode("ascii")
    html = f"""<html><head><title>{TITLE}</title></head><body>
<h1>{H1}</h1>
<h2>{H2_A}</h2>
<p>{PARA_A}</p>
<p>{PARA_A2}</p>
<ul>{"".join(f"<li>{item}</li>" for item in LIST_A)}</ul>
<table>
<tr>{"".join(f"<th>{h}</th>" for h in TABLE_HEADER)}</tr>
{"".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in TABLE_ROWS)}
</table>
<h2>{H2_B}</h2>
<p>{PARA_B}</p>
<img src="{image_data_uri}" alt="organelle diagram" />
</body></html>
"""
    (FIXTURES_DIR / "study_notes.html").write_text(html)


def generate_docx() -> None:
    from docx import Document
    from docx.shared import Inches

    doc = Document()
    doc.add_heading(H1, level=1)
    doc.add_heading(H2_A, level=2)
    doc.add_paragraph(PARA_A)
    doc.add_paragraph(PARA_A2)
    for item in LIST_A:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(item)
    table = doc.add_table(rows=1, cols=2)
    for cell, header in zip(table.rows[0].cells, TABLE_HEADER, strict=True):
        cell.text = header
    for row_values in TABLE_ROWS:
        row = table.add_row()
        for cell, value in zip(row.cells, row_values, strict=True):
            cell.text = value
    doc.add_heading(H2_B, level=2)
    doc.add_paragraph(PARA_B)
    png_path = _tiny_png_path(FIXTURES_DIR)
    doc.add_picture(str(png_path), width=Inches(1))
    png_path.unlink()
    doc.save(FIXTURES_DIR / "study_notes.docx")


def generate_pptx() -> None:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = H1
    body = slide.placeholders[1].text_frame
    body.text = H2_A
    for item in LIST_A:
        p = body.add_paragraph()
        p.text = item

    slide2 = prs.slides.add_slide(prs.slide_layouts[5])
    slide2.shapes.title.text = H2_B
    png_path = _tiny_png_path(FIXTURES_DIR)
    slide2.shapes.add_picture(
        str(png_path), Inches(1), Inches(1.5), height=Inches(1), width=Inches(1)
    )
    png_path.unlink()

    table_shape = slide2.shapes.add_table(
        len(TABLE_ROWS) + 1, len(TABLE_HEADER), Inches(1), Inches(3), Inches(4), Inches(1.2)
    )
    table = table_shape.table
    for col, header in enumerate(TABLE_HEADER):
        table.cell(0, col).text = header
    for row_idx, row_values in enumerate(TABLE_ROWS, start=1):
        for col, value in enumerate(row_values):
            table.cell(row_idx, col).text = value

    prs.save(FIXTURES_DIR / "study_notes.pptx")


def generate_pdf() -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        Image,
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Table,
    )

    styles = getSampleStyleSheet()
    target = FIXTURES_DIR / "study_notes.pdf"
    doc = SimpleDocTemplate(str(target), pagesize=letter)
    story = [
        Paragraph(H1, styles["Heading1"]),
        Paragraph(H2_A, styles["Heading2"]),
        Paragraph(PARA_A, styles["Normal"]),
        Paragraph(PARA_A2, styles["Normal"]),
        ListFlowable([ListItem(Paragraph(item, styles["Normal"])) for item in LIST_A]),
        Table([TABLE_HEADER, *TABLE_ROWS]),
        PageBreak(),
        Paragraph(H2_B, styles["Heading2"]),
        Paragraph(PARA_B, styles["Normal"]),
    ]
    png_path = _tiny_png_path(FIXTURES_DIR)
    story.append(Image(str(png_path), width=40, height=40))
    doc.build(story)
    png_path.unlink()


def generate_misc() -> None:
    (FIXTURES_DIR / "unsupported.txt").write_text("Plain text is not a supported upload type.\n")
    (FIXTURES_DIR / "empty.pdf").write_bytes(b"")
    (FIXTURES_DIR / "corrupted.pdf").write_bytes(
        b"%PDF-1.4 this is not a real pdf body \x00\x01\x02"
    )


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    generate_html()
    generate_docx()
    generate_pptx()
    generate_pdf()
    generate_misc()
    print(f"Wrote fixtures to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
