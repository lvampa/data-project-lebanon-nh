import pendulum
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="city_staff",
    schedule="0 4 1 * *",
    start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
    catchup=False,
    tags=["staff"],
) as dag:
    BashOperator(
        task_id="scrape_city_staff",
        bash_command="cd /opt/project/scrapers && uv run --frozen scrapy crawl city_staff",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
