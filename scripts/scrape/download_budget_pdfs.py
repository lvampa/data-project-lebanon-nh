"""
Download budget PDFs and extract text for the Claude Code agent handoff.

Run from repo root:
    uv run python scripts/scrape/download_budget_pdfs.py

Reads:  budget_documents rows where text_extracted = false
Writes: scripts/data/budgets/{year}-{type}.txt
"""

import urllib.request
from pathlib import Path

import logfire
import pypdf
from postgres import SessionLocal
from postgres.models.budget_document import BudgetDocument
from sqlalchemy import select

DATA_DIR = Path(__file__).parents[1] / "data" / "budgets"


def output_path(fiscal_year: int, document_type: str) -> Path:
    return DATA_DIR / f"{fiscal_year}-{document_type}.txt"


def extract_text(pdf_path: Path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def download_pdf(url: str, dest: Path) -> None:
    urllib.request.urlretrieve(url, dest)


def main() -> None:
    logfire.configure()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session:
        docs = (
            session.execute(
                select(BudgetDocument).where(BudgetDocument.text_extracted == False)  # noqa: E712
            )
            .scalars()
            .all()
        )

        if not docs:
            logfire.info("all budget documents already extracted")
            return

        for doc in docs:
            with logfire.span(
                "download budget pdf",
                fiscal_year=doc.fiscal_year,
                document_type=doc.document_type,
            ):
                pdf_path = DATA_DIR / f"{doc.fiscal_year}-{doc.document_type}.pdf"
                download_pdf(doc.source_url, pdf_path)
                text = extract_text(pdf_path)
                txt_path = output_path(doc.fiscal_year, doc.document_type)
                txt_path.write_text(text, encoding="utf-8")
                doc.text_extracted = True
                session.commit()
                logfire.info(
                    "extracted {chars} chars",
                    chars=len(text),
                    fiscal_year=doc.fiscal_year,
                    document_type=doc.document_type,
                )


if __name__ == "__main__":
    main()
