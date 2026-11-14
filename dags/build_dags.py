from datetime import timedelta
from pathlib import PurePosixPath

import pendulum
from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from specs import SPECS, DagSpec

PROJECT_ROOT = PurePosixPath("/opt/project")


def build_dag(spec: DagSpec) -> DAG:
    with DAG(
        dag_id=spec.dag_id,
        schedule=spec.schedule,
        start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
        catchup=False,
        # A slow vgsi_property crawl must not overlap next week's run.
        max_active_runs=1,
        params={name: Param(**kwargs) for name, kwargs in spec.params.items()},
        tags=list(spec.tags),
    ) as dag:
        run = BashOperator(
            task_id=spec.dag_id,
            bash_command=f"cd {PROJECT_ROOT / spec.cwd} && uv run --frozen {spec.command}",
            execution_timeout=spec.timeout,
            retries=1,
            retry_delay=timedelta(minutes=5),
        )
        for target in spec.triggers:
            run >> TriggerDagRunOperator(
                task_id=f"trigger_{target}",
                trigger_dag_id=target,
                wait_for_completion=False,
            )
    return dag


# DagBag collects the DAG objects it finds in module globals.
for spec in SPECS:
    globals()[spec.dag_id] = build_dag(spec)
