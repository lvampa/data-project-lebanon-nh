import scrapy


class UrlRecordItem(scrapy.Item):
    canonical_url = scrapy.Field()
    archive_url = scrapy.Field()
    log_date = scrapy.Field()
    state = scrapy.Field()
    created_at = scrapy.Field()
