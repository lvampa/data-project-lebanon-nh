import scrapy


class DailyLogSpider(scrapy.Spider):
    name = "daily_log"
    start_urls = ["https://www.lebanonnh.gov/232/Daily-Police-Log"]

    def parse(self, response):
        # TODO: find PDF links and yield requests to parse_pdf
        pass

    def parse_pdf(self, response, link_text: str):
        # TODO: extract text from PDF with pypdf and yield a PoliceLogItem
        pass
