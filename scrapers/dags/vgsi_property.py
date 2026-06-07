import pendulum
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="vgsi_property",
    schedule="0 3 * * 0",  # 3am every Sunday
    start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
    catchup=False,
    tags=["property"],
) as dag:
    BashOperator(
        task_id="scrape_vgsi",
        bash_command="cd /opt/project/scrapers && uv run scrapy crawl vgsi_property",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
