import pendulum
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.models.param import Param

with DAG(
    dag_id="process_urls",
    schedule=None,  # triggered by discover_urls; can also be run manually
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    params={
        "limit": Param(50, type="integer", description="Max URLs to process per run"),
    },
    tags=["police-log"],
) as dag:
    BashOperator(
        task_id="process_urls",
        bash_command=(
            "cd /opt/project/scrapers && "
            "uv run --frozen scrapy crawl process_urls -a limit='{{ params.limit }}'"
        ),
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
