import scrapy


class DownloadedUrlItem(scrapy.Item):
    url_doc_id = scrapy.Field()     # ObjectId of the urls document
    state = scrapy.Field()          # "downloaded" or "error"
    pdf_data = scrapy.Field()       # Raw PDF bytes (only set on success)
    downloaded_at = scrapy.Field()  # datetime (only set on success)
