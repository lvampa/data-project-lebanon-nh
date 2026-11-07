import scrapy


class PoliceLogPdfItem(scrapy.Item):
    """One downloaded log PDF. The pipeline parses its text and stores the entries."""

    url_id = scrapy.Field()
    raw_text = scrapy.Field()
    # The SHA-256 of the downloaded bytes, so the pipeline can record which archived
    # original it read without waiting for the archive's batch write.
    content_hash = scrapy.Field()
