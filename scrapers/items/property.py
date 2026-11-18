import scrapy


class PropertyItem(scrapy.Item):
    """One VGSI parcel page. Every value is the text the page printed, or a list or
    dict of that text. PropertyRecord converts them."""

    parcel_id = scrapy.Field()  # VGSI pid, the key in the parcel page's URL
    location = scrapy.Field()  # street address
    owner = scrapy.Field()
    co_owner = scrapy.Field()
    owner_address = scrapy.Field()  # the owner's mailing address
    mblu = scrapy.Field()  # map, block, lot, unit
    account_number = scrapy.Field()
    use_code = scrapy.Field()
    land_use = scrapy.Field()  # the use code's description
    zone = scrapy.Field()
    neighborhood = scrapy.Field()
    lot_size_acres = scrapy.Field()
    year_built = scrapy.Field()
    building_sqft = scrapy.Field()
    assessed_land = scrapy.Field()
    assessed_building = scrapy.Field()
    assessed_total = scrapy.Field()
    assessment_year = scrapy.Field()
    appraised_land = scrapy.Field()
    appraised_building = scrapy.Field()
    appraised_total = scrapy.Field()
    land = scrapy.Field()  # dict of the land tables' rows
    buildings = scrapy.Field()  # list of dicts, one per building section
    outbuildings = scrapy.Field()  # list of dicts
    extra_features = scrapy.Field()  # list of dicts
    value_history = scrapy.Field()  # {"assessment": [...], "appraisal": [...]}
    detail_url = scrapy.Field()
    # One dict per row of the ownership history: owner, sale_price, certificate,
    # book_page, instrument, sale_date.
    sales = scrapy.Field()
