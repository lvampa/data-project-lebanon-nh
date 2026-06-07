import pendulum
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models.param import Param

with DAG(
    dag_id="discover_urls",
    schedule="0 6 * * 1",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    params={
        "url": Param(
            "https://www.lebanonnh.gov/232/Daily-Police-Log",
            type="string",
            description="City page URL or Wayback Machine snapshot URL to crawl",
        ),
    },
    tags=["police-log"],
) as dag:
    build = BashOperator(
        task_id="build_daily_urls",
        bash_command=(
            "cd /opt/project/scrapers && "
            "uv run scrapy crawl build_daily_urls -a url='{{ params.url }}'"
        ),
        retries=1,
        retry_delay=timedelta(minutes=5),
    )

    trigger = TriggerDagRunOperator(
        task_id="trigger_process_urls",
        trigger_dag_id="process_urls",
        wait_for_completion=False,
    )

    build >> trigger
