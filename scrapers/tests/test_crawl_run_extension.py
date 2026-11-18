from datetime import datetime
from types import SimpleNamespace

import pytest
from extensions import CrawlRunExtension
from postgres.models.crawl_run import CrawlRun

SPIDER = SimpleNamespace(name="city_staff")


class FakeStats:
    def get_stats(self, spider: object) -> dict[str, int]:
        return {"downloader/response_count": 12}


@pytest.fixture
def extension() -> CrawlRunExtension:
    return CrawlRunExtension(FakeStats())  # type: ignore[arg-type]


def test_a_finished_crawl_records_its_source_and_pages(db_session, extension):
    extension.spider_opened(SPIDER)  # type: ignore[arg-type]

    extension.spider_closed(SPIDER, "finished")  # type: ignore[arg-type]

    run = db_session.get(CrawlRun, extension.run_id)
    assert run is not None
    assert (run.source, run.pages) == ("city_staff", 12)
    assert isinstance(run.finished_at, datetime)


def test_a_stopped_crawl_stays_unfinished(db_session, extension):
    extension.spider_opened(SPIDER)  # type: ignore[arg-type]

    extension.spider_closed(SPIDER, "shutdown")  # type: ignore[arg-type]

    run = db_session.get(CrawlRun, extension.run_id)
    assert run is not None
    assert run.finished_at is None
