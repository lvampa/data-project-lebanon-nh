from pydantic import BaseModel


class PdfUrlClaim(BaseModel):
    id: int
    canonical_url: str
    archive_url: str | None = None
