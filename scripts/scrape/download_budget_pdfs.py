"""
Download budget PDFs and extract text for the Claude Code agent handoff.

Run from repo root:
    uv run python scripts/scrape/download_budget_pdfs.py

Reads:  budget_documents rows that are not extracted, or whose text file is gone
Writes: scripts/data/budgets/{year}-{type}.txt
"""

from pathlib import Path

import httpx
import logfire
import pypdf
from postgres import SessionLocal
from postgres.models.budget_document import BudgetDocument
from sqlalchemy import select

DATA_DIR = Path(__file__).parents[1] / "data" / "budgets"
USER_AGENT = "lebanon-nh-data/1.0 (+https://github.com/lvampa/Data-Project-Lebanon-NH)"
DOWNLOAD_TIMEOUT = httpx.Timeout(10.0, read=60.0)


def output_path(fiscal_year: int, document_type: str) -> Path:
    return DATA_DIR / f"{fiscal_year}-{document_type}.txt"


def documents_needing_text(docs: list[BudgetDocument]) -> list[BudgetDocument]:
    # text_extracted only says the file was written once. The text lives on
    # disk, so a lost file means the work has to be redone.
    return [
        doc
        for doc in docs
        if not doc.text_extracted
        or not output_path(doc.fiscal_year, doc.document_type).exists()
    ]


def extract_text(pdf_path: Path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=DOWNLOAD_TIMEOUT,
        follow_redirects=True,
    )


def download_pdf(client: httpx.Client, url: str, dest: Path) -> None:
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)


def main() -> None:
    logfire.configure()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session, make_client() as client:
        all_docs = session.execute(select(BudgetDocument)).scalars().all()
        docs = documents_needing_text(all_docs)

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
                download_pdf(client, doc.source_url, pdf_path)
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
