import scrapy


class PropertyItem(scrapy.Item):
    parcel_id = scrapy.Field()       # VGSI map/lot/sub identifier
    location = scrapy.Field()        # street address
    owner = scrapy.Field()
    owner_address = scrapy.Field()
    land_use = scrapy.Field()
    lot_size_acres = scrapy.Field()  # string from HTML, pipeline converts
    year_built = scrapy.Field()
    building_sqft = scrapy.Field()
    assessed_land = scrapy.Field()
    assessed_building = scrapy.Field()
    assessed_total = scrapy.Field()
    assessment_year = scrapy.Field()
    detail_url = scrapy.Field()
    sales = scrapy.Field()           # list of sale dicts: {sale_date, sale_price, grantor, grantee}
