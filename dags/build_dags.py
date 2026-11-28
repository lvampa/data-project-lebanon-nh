from datetime import timedelta
from pathlib import PurePosixPath

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import DAG, BaseHook, Param
from publish import run_with_r2
from specs import SPECS, DagSpec

PROJECT_ROOT = PurePosixPath("/opt/project")


def command_of(spec: DagSpec) -> str:
    return f"cd {PROJECT_ROOT / spec.cwd} && uv run --frozen {spec.command}"


def run_with_connection(spec: DagSpec) -> None:
    """Read the Connection when the task runs, and give it to the command's environment only."""
    assert spec.connection is not None
    run_with_r2(
        ["uv", "run", "--frozen", *spec.command.split()],
        str(PROJECT_ROOT / spec.cwd),
        BaseHook.get_connection(spec.connection),
    )


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
        run: BashOperator | PythonOperator
        if spec.connection:
            run = PythonOperator(
                task_id=spec.dag_id,
                python_callable=run_with_connection,
                op_kwargs={"spec": spec},
                execution_timeout=spec.timeout,
                retries=1,
                retry_delay=timedelta(minutes=5),
            )
        else:
            run = BashOperator(
                task_id=spec.dag_id,
                bash_command=command_of(spec),
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
