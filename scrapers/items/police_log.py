import scrapy


class PoliceLogPdfItem(scrapy.Item):
    """One downloaded log PDF. The pipeline parses its text and stores the entries."""

    url_id = scrapy.Field()
    raw_text = scrapy.Field()
