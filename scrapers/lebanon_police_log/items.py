import scrapy


class PoliceLogItem(scrapy.Item):
    source_url = scrapy.Field()    # URL of the PDF
    pdf_filename = scrapy.Field()  # Original filename
    log_date = scrapy.Field()      # Date parsed from filename/link text
    raw_text = scrapy.Field()      # Full extracted text from PDF
    scraped_at = scrapy.Field()    # Timestamp
