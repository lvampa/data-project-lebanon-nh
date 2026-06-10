from pathlib import Path

import logfire
from sqlalchemy import select

from postgres import SessionLocal
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = DATA_DIR / "incident_types.txt"


def fetch_uncategorized(session) -> list[str]:
    already = select(IncidentTypeCategory.raw_incident_type)
    stmt = (
        select(LogEntry.incident_type)
        .where(
            LogEntry.incident_type.isnot(None),
            LogEntry.incident_type != "",
            LogEntry.incident_type.not_in(already),
        )
        .distinct()
        .order_by(LogEntry.incident_type)
    )
    return session.execute(stmt).scalars().all()


def main() -> None:
    logfire.configure()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as session:
        with logfire.span("export incident types"):
            types = fetch_uncategorized(session)
            if not types:
                logfire.info("nothing to export — all types already categorized")
                return
            OUTPUT_FILE.write_text("\n".join(types), encoding="utf-8")
            logfire.info(
                "exported {count} incident types",
                count=len(types),
                path=str(OUTPUT_FILE),
            )


if __name__ == "__main__":
    main()
