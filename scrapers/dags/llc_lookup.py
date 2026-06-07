from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="llc_lookup",
    schedule="0 4 * * 0",  # 4am every Sunday (after vgsi_property at 3am)
    start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
    catchup=False,
    tags=["property", "llc"],
) as dag:
    BashOperator(
        task_id="scrape_llcs",
        bash_command="cd /opt/project && uv run --frozen python scripts/scrape_llcs.py --limit 50",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
