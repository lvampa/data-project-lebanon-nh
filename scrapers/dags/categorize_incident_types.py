# scrapers/dags/categorize_incident_types.py
import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="categorize_incident_types",
    schedule="0 6 * * 1",  # 6am every Monday — runs after weekly police log scrape
    start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
    catchup=False,
    tags=["enrichment"],
) as dag:
    BashOperator(
        task_id="categorize",
        bash_command=(
            "cd /opt/scrapers && "
            "uv run python scripts/categorize_incident_types.py --mode cli"
        ),
    )
