from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1] / "deploy.sh"

# The deploy runs these in this order. Each marker is found in the script's own lines.
ORDER = [
    "dbt build --project-dir transform --profiles-dir transform",
    "generate_report.sh",
    "report-gen --release -- check --dir",
    "bun run build",
    "wrangler pages deploy",
]


def commands() -> list[str]:
    lines = [line.strip() for line in DEPLOY.read_text().splitlines()]
    return [line for line in lines if line and not line.startswith(("#", "echo"))]


def test_the_deploy_stops_on_the_first_failure():
    assert "set -e" in commands()


def test_the_data_checks_and_the_export_check_run_before_anything_is_built_or_uploaded():
    steps = commands()
    positions = [
        next(i for i, line in enumerate(steps) if marker in line) for marker in ORDER
    ]

    assert positions == sorted(positions)


def test_the_disposition_seed_is_written_before_the_dbt_build():
    steps = commands()
    seed = next(i for i, line in enumerate(steps) if "write_disposition_seed" in line)
    build = next(i for i, line in enumerate(steps) if "dbt build" in line)

    assert seed < build


def test_a_database_url_stops_the_deploy_before_dbt_runs():
    steps = commands()
    guard = next(i for i, line in enumerate(steps) if "DATABASE_URL" in line)
    build = next(i for i, line in enumerate(steps) if "dbt build" in line)

    assert guard < build
    assert "exit 1" in steps[guard + 1 : build]
