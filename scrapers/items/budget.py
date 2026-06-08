import scrapy


class BudgetDocumentItem(scrapy.Item):
    fiscal_year = scrapy.Field()
    document_type = scrapy.Field()  # 'budget_book' | 'line_items'
    source_url = scrapy.Field()
    scraped_at = scrapy.Field()
