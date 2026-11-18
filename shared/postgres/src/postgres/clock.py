from datetime import UTC, datetime


def utc_now() -> datetime:
    """Now as a naive datetime. The database's timestamp columns hold naive UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_naive_utc(moment: datetime) -> datetime:
    """A moment as naive UTC. A naive moment is taken to be UTC already."""
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)
