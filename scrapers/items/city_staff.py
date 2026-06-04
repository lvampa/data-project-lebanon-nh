import scrapy


class CityStaffItem(scrapy.Item):
    name = scrapy.Field()
    title = scrapy.Field()
    department = scrapy.Field()
    division = scrapy.Field()
    email = scrapy.Field()
    phone = scrapy.Field()
    source_url = scrapy.Field()
    scraped_at = scrapy.Field()
