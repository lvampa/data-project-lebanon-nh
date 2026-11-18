from datetime import UTC, datetime

from postgres import open_session
from postgres.models.crawl_run import CrawlRun


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def start_run(source: str) -> int:
    with open_session() as session:
        run = CrawlRun(source=source, started_at=_now())
        session.add(run)
        session.commit()
        return run.id


def finish_run(run_id: int, pages: int) -> None:
    """A run that never gets here keeps no finished_at, and builds ignore it."""
    with open_session() as session:
        run = session.get(CrawlRun, run_id)
        assert run is not None
        run.finished_at = _now()
        run.pages = pages
        session.commit()
