import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
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
    BashOperator(
        task_id="build_daily_urls",
        bash_command=(
            "cd /opt/project/scrapers && "
            "uv run scrapy crawl build_daily_urls -a url='{{ params.url }}'"
        ),
    )
