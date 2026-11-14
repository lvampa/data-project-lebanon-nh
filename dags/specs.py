"""Every scheduled job, as plain data so it can be tested without Airflow.

build_dags.py turns each spec into a DAG with one task that runs
`uv run --frozen <command>` from `/opt/project/<cwd>`, then one task per
entry in `triggers` that starts that DAG.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any


@dataclass(frozen=True)
class DagSpec:
    dag_id: str
    # A cron expression, or None for DAGs that another DAG triggers.
    schedule: str | None
    command: str
    timeout: timedelta
    tags: tuple[str, ...]
    cwd: str = "."
    triggers: tuple[str, ...] = ()
    # Keyword arguments for airflow.models.param.Param, keyed by param name.
    params: dict[str, dict[str, Any]] = field(default_factory=dict)


SPECS = [
    DagSpec(
        dag_id="discover_urls",
        schedule="0 6 * * 1",  # 6am every Monday
        cwd="scrapers",
        command="scrapy crawl build_daily_urls -a url='{{ params.url }}'",
        timeout=timedelta(hours=1),
        tags=("police-log",),
        triggers=("process_urls",),
        params={
            "url": {
                "default": "https://www.lebanonnh.gov/232/Daily-Police-Log",
                "type": "string",
                "description": "City page URL or Wayback Machine snapshot URL to crawl",
            },
        },
    ),
    DagSpec(
        dag_id="process_urls",
        schedule=None,
        cwd="scrapers",
        # The runner exits non-zero when a PDF fails; `scrapy crawl` always exits 0.
        command="python run_process_urls.py --limit '{{ params.limit }}'",
        timeout=timedelta(hours=2),
        tags=("police-log",),
        triggers=("sync_elasticsearch",),
        params={
            "limit": {
                "default": 50,
                "type": "integer",
                "description": "Max URLs to process per run",
            },
        },
    ),
    DagSpec(
        dag_id="vgsi_property",
        schedule="0 3 * * 0",  # 3am every Sunday
        cwd="scrapers",
        command="scrapy crawl vgsi_property",
        # Every parcel, one request at a time with autothrottle: several hours.
        timeout=timedelta(hours=12),
        tags=("property",),
        triggers=("llc_lookup",),
    ),
    DagSpec(
        dag_id="llc_lookup",
        schedule=None,
        command="python scripts/scrape/scrape_llcs.py --limit 50",
        timeout=timedelta(hours=1),
        tags=("property", "llc"),
        triggers=("sync_elasticsearch",),
    ),
    DagSpec(
        dag_id="civicclerk_planning",
        schedule="0 5 * * *",  # 5am daily
        command="python scripts/scrape/scrape_civicclerk.py",
        timeout=timedelta(hours=2),
        tags=("planning",),
        triggers=("sync_elasticsearch",),
    ),
    DagSpec(
        dag_id="city_staff",
        schedule="0 4 1 * *",  # 4am on the 1st of every month
        cwd="scrapers",
        command="scrapy crawl city_staff",
        timeout=timedelta(hours=1),
        tags=("staff",),
        triggers=("sync_elasticsearch",),
    ),
    DagSpec(
        dag_id="officer_roster",
        schedule="0 4 1 * *",  # 4am on the 1st of every month
        cwd="scrapers",
        command="scrapy crawl officer_roster",
        timeout=timedelta(hours=1),
        tags=("officers",),
        triggers=("sync_elasticsearch",),
    ),
    DagSpec(
        dag_id="budget_discovery",
        # Monthly because the budget publish date varies. Budget documents are
        # not indexed, so this does not trigger the Elasticsearch sync.
        schedule="0 4 1 * *",
        cwd="scrapers",
        command="scrapy crawl budget_discovery",
        timeout=timedelta(hours=1),
        tags=("budget",),
    ),
    DagSpec(
        dag_id="mongo_backup",
        schedule="0 2 * * *",  # 2am daily
        cwd="scrapers",
        # The raw source archive holds the only copy of some originals.
        command="python maintenance/mongo_backup.py",
        timeout=timedelta(hours=1),
        tags=("archive",),
    ),
    DagSpec(
        dag_id="sync_elasticsearch",
        schedule=None,
        command="python scripts/sync/sync_es.py",
        timeout=timedelta(hours=1),
        tags=("sync",),
    ),
]
