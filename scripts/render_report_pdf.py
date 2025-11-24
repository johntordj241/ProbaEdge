#!/usr/bin/env python3
"""
Render a lightweight PDF report from a Markdown-like text file.

This helper avoids extra dependencies by emitting a basic PDF with
Helvetica / Helvetica-Bold fonts and simple text wrapping.
It is intentionally limited but good enough for concise status reports.
"""

from __future__ import annotations

import argparse
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

PAGE_WIDTH = 595.28  # A4 in points (72 DPI)
PAGE_HEIGHT = 841.89
MARGIN = 48.0
REGULAR_FONT = "F1"
BOLD_FONT = "F2"


@dataclass
class LineSpec:
    text: str
    font: str
    size: float
    leading: float


def parse_markdown(raw: str) -> List[LineSpec]:
    """Convert a small Markdown subset into printable line specs."""
    lines: List[LineSpec] = []
    wrapper = textwrap.TextWrapper(width=90, break_long_words=False, break_on_hyphens=False)
    bullet_wrapper = textwrap.TextWrapper(
        width=86, subsequent_indent="    ", break_long_words=False, break_on_hyphens=False
    )
    for chunk in raw.splitlines():
        stripped = chunk.strip()
        if not stripped:
            lines.append(LineSpec("", REGULAR_FONT, 6, 10))
            continue
        if stripped.startswith("### "):
            lines.append(LineSpec(stripped[4:], BOLD_FONT, 12, 20))
            continue
        if stripped.startswith("## "):
            lines.append(LineSpec(stripped[3:], BOLD_FONT, 14, 24))
            continue
        if stripped.startswith("# "):
            lines.append(LineSpec(stripped[2:], BOLD_FONT, 16, 28))
            continue
        if stripped.startswith("- "):
            body = stripped[2:]
            wrapped = bullet_wrapper.wrap(body) or [body]
            first = f"- {wrapped[0]}"
            lines.append(LineSpec(first, REGULAR_FONT, 11, 16))
            for continuation in wrapped[1:]:
                lines.append(LineSpec(continuation, REGULAR_FONT, 11, 16))
            continue
        wrapped = wrapper.wrap(stripped) or [stripped]
        for entry in wrapped:
            lines.append(LineSpec(entry, REGULAR_FONT, 11, 16))
    return lines


def escape_pdf_text(text: str) -> str:
    """Escape parentheses and backslashes for PDF literal strings."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def chunk_pages(lines: Sequence[LineSpec]) -> List[List[Tuple[str, float, float, LineSpec]]]:
    """Split line specs into pages with coordinates."""
    pages: List[List[Tuple[str, float, float, LineSpec]]] = []
    y = PAGE_HEIGHT - MARGIN
    current: List[Tuple[str, float, float, LineSpec]] = []
    for spec in lines:
        needed = spec.leading if spec.text else spec.leading / 2
        if y - needed < MARGIN:
            pages.append(current)
            current = []
            y = PAGE_HEIGHT - MARGIN
        y -= needed
        current.append(("%.2f" % MARGIN, "%.2f" % y, spec))
    if current:
        pages.append(current)
    if not pages:
        pages.append([])
    return pages


def build_content_stream(page: List[Tuple[str, float, float, LineSpec]]) -> bytes:
    if not page:
        return b""
    parts: List[str] = []
    for x, y, spec in page:
        if not spec.text:
            continue
        parts.append(
            f"BT /{spec.font} {spec.size:.1f} Tf 1 0 0 1 {x} {y} Tm ({escape_pdf_text(spec.text)}) Tj ET"
        )
    joined = "\n".join(parts)
    return joined.encode("utf-8")


def build_pdf(pages: List[bytes]) -> bytes:
    """Assemble a minimal PDF from page content streams."""
    objects: List[bytes] = []

    # 1: Catalog placeholder (points to Pages -> object 2)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    # 2: Pages dictionary (Kids will be filled later)
    kids = " ".join(f"{idx + 3} 0 R" for idx in range(len(pages)))
    objects.append(
        f"<< /Type /Pages /Count {len(pages)} /Kids [{kids}] >>".encode("utf-8")
    )

    # 3..n: Page objects + contents
    page_objects: List[bytes] = []
    content_objects: List[bytes] = []
    for idx, content in enumerate(pages):
        content_obj_number = len(objects) + len(page_objects) + len(content_objects) + 2
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f}] "
            f"/Contents {content_obj_number} 0 R /Resources << /Font << /{REGULAR_FONT}  {content_obj_number + 1} 0 R "
            f"/{BOLD_FONT} {content_obj_number + 2} 0 R >> >> >>"
        ).encode("utf-8")
        page_objects.append(page_dict)
        content_objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode("utf-8") + content + b"\nendstream"
        )
    objects.extend(page_objects)
    objects.extend(content_objects)

    # Font objects (Helvetica regular and bold)
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    # Build final PDF with xref
    pdf_parts: List[bytes] = [b"%PDF-1.4\n"]
    offsets: List[int] = [0]
    for obj_id, body in enumerate(objects, start=1):
        offsets.append(len(b"".join(pdf_parts)))
        pdf_parts.append(f"{obj_id} 0 obj\n".encode("utf-8"))
        pdf_parts.append(body)
        pdf_parts.append(b"\nendobj\n")

    xref_offset = len(b"".join(pdf_parts))
    pdf_parts.append(b"xref\n0 %d\n" % (len(objects) + 1))
    pdf_parts.append(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf_parts.append(f"{off:010d} 00000 n \n".encode("utf-8"))
    trailer = (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode("utf-8")
    pdf_parts.append(trailer)
    return b"".join(pdf_parts)


def render_pdf(input_path: Path, output_path: Path) -> None:
    text = input_path.read_text(encoding="utf-8")
    specs = parse_markdown(text)
    pages = [build_content_stream(page) for page in chunk_pages(specs)]
    pdf_bytes = build_pdf(pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)
    print(f"PDF generated at {output_path}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Convert a Markdown file into a simple PDF report.")
    parser.add_argument("--input", required=True, type=Path, help="Source Markdown/texte")
    parser.add_argument("--output", required=True, type=Path, help="Chemin cible PDF")
    args = parser.parse_args(argv)
    render_pdf(args.input, args.output)


if __name__ == "__main__":
    main()
