import io

from pypdf import PdfReader


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """The text of a log PDF, as the parser reads it.

    The process job and the reprocess job both call this, so a pypdf change moves
    both together (see EXTRACTOR_VERSION).
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)
