from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="officer_roster",
    schedule="0 4 1 * *",  # 4am on the 1st of every month
    start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
    catchup=False,
    tags=["officers"],
) as dag:
    BashOperator(
        task_id="scrape_officer_roster",
        bash_command="cd /opt/project/scrapers && uv run --frozen scrapy crawl officer_roster",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
