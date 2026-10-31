from types import SimpleNamespace

import pytest
from models.pdf_url_claim import PdfUrlClaim
from pydantic import ValidationError


def test_reads_a_returned_row():
    row = SimpleNamespace(
        id=7, canonical_url="https://example.com/a.pdf", archive_url=None
    )

    claim = PdfUrlClaim.model_validate(row, from_attributes=True)

    assert claim.id == 7
    assert claim.canonical_url == "https://example.com/a.pdf"
    assert claim.archive_url is None


def test_archive_url_optional():
    claim = PdfUrlClaim(id=7, canonical_url="https://example.com/a.pdf")
    assert claim.archive_url is None


def test_requires_canonical_url():
    with pytest.raises(ValidationError):
        PdfUrlClaim(id=7)
