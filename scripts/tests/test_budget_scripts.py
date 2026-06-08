from pathlib import Path

import pytest

from scripts.download_budget_pdfs import extract_text, output_path


# --- output_path ---

def test_output_path_budget_book():
    p = output_path(2026, "budget_book")
    assert p.name == "2026-budget_book.txt"
    assert p.parent.name == "budgets"


def test_output_path_line_items():
    p = output_path(2025, "line_items")
    assert p.name == "2025-line_items.txt"


# --- extract_text ---

def test_extract_text_returns_string(tmp_path):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    pdf_path = tmp_path / "test.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)
    result = extract_text(pdf_path)
    assert isinstance(result, str)


def test_extract_text_joins_pages(tmp_path):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    pdf_path = tmp_path / "two_page.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)
    result = extract_text(pdf_path)
    assert isinstance(result, str)
