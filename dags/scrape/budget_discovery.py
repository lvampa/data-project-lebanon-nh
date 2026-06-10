from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="budget_discovery",
    schedule="0 4 1 * *",  # 4am on the 1st of every month (budget publish date varies)
    start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
    catchup=False,
    tags=["budget"],
) as dag:
    BashOperator(
        task_id="scrape_budget_discovery",
        bash_command="cd /opt/project/scrapers && uv run --frozen scrapy crawl budget_discovery",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
