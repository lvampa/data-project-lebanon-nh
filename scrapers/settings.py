# Scrapy settings
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "scrapers"

SPIDER_MODULES = ["spiders"]
NEWSPIDER_MODULE = "spiders"

ADDONS = {}


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Concurrency and throttling
CONCURRENT_REQUESTS_PER_DOMAIN = 1
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# Disable cookies (enabled by default)
# COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# The raw archive is a spider middleware, so it runs after Scrapy attaches the request
# to the response, and after the built-in HttpErrorMiddleware (50), which stops non-2xx
# responses before the callback. process_spider_input runs from the lowest number up.
SPIDER_MIDDLEWARES = {
    "middlewares.raw_archive.RawArchiveMiddleware": 100,
}

# Spiders with archive_source keep their originals in MongoDB. Turn it off for a
# spider with custom_settings = {"RAW_ARCHIVE_ENABLED": False}.
RAW_ARCHIVE_ENABLED = True

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
EXTENSIONS = {
    "extensions.LogfireExtension": 100,
    "extensions.CrawlRunExtension": 200,
}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "pipelines.UrlRecordPipeline": 100,
    "pipelines.PoliceLogPipeline": 300,
    "pipelines.CityStaffPipeline": 500,
    "pipelines.OfficerPipeline": 600,
    "pipelines.BudgetDocumentPipeline": 700,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
# AUTOTHROTTLE_ENABLED = True
# The initial download delay
# AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
# AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
# AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
# AUTOTHROTTLE_DEBUG = False

# HTTP cache — enabled in dev via SCRAPY_HTTPCACHE=1 to avoid re-downloading PDFs
import os as _os

if _os.environ.get("SCRAPY_HTTPCACHE"):
    HTTPCACHE_ENABLED = True
    HTTPCACHE_EXPIRATION_SECS = 86400  # 1 day
    HTTPCACHE_DIR = ".httpcache"
    HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504]

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"
