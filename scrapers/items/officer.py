import scrapy


class OfficerItem(scrapy.Item):
    name = scrapy.Field()
    rank = scrapy.Field()
    division = scrapy.Field()
    email = scrapy.Field()
    phone = scrapy.Field()
    source_url = scrapy.Field()
    scraped_at = scrapy.Field()
