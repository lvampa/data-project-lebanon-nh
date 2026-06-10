from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="sync_elasticsearch",
    schedule="0 3 * * *",  # 3am nightly, after scrapers have run
    start_date=pendulum.datetime(2026, 6, 10, tz="UTC"),
    catchup=False,
    tags=["sync"],
) as dag:
    BashOperator(
        task_id="sync_es",
        bash_command="cd /opt/project && uv run --frozen python scripts/sync/sync_es.py",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
