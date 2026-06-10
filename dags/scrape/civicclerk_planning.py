from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="civicclerk_planning",
    schedule="0 5 * * *",
    start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
    catchup=False,
    tags=["planning"],
) as dag:
    BashOperator(
        task_id="scrape_planning_board",
        bash_command="cd /opt/project && uv run --frozen python scripts/scrape/scrape_civicclerk.py",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
