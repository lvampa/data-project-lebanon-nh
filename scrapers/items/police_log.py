import scrapy


class PoliceLogPdfItem(scrapy.Item):
    """One downloaded log PDF. The pipeline parses its text and stores the entries."""

    url_id = scrapy.Field()
    raw_text = scrapy.Field()
    # The SHA-256 of the downloaded bytes, so the pipeline can record which archived
    # original it read.
    content_hash = scrapy.Field()
    # Whether the raw archive kept the downloaded bytes. Without them, a parse or
    # save error has to download the PDF again.
    original_archived = scrapy.Field()
