"""The columns both lookup tables share: who produced a value, and how it is doing.

A row may exist with no normalized value. That is where failed attempts and the
review mark live for a raw value the AI has not answered. A row with a `human`
source is never overwritten by a rule or by AI.
"""

from sqlalchemy import Boolean, CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

SOURCES = ("rule", "ai", "human")


class ProvenanceMixin:
    # Null while the value waits. `rule` is used only for locations.
    source: Mapped[str | None] = mapped_column(Text)
    # The effective prompt version of the AI answer, or `rules-<RULES_VERSION>` for a
    # rule row. Null for `human`. `--redo` skips rows already on the current version.
    prompt_version: Mapped[str | None] = mapped_column(Text)
    # The ai_calls document in MongoDB that produced the last AI answer. It stays
    # when a human takes over the value.
    ai_call_id: Mapped[str | None] = mapped_column(Text)
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


def source_check(table_name: str) -> CheckConstraint:
    allowed = ", ".join(f"'{source}'" for source in SOURCES)
    return CheckConstraint(f"source IN ({allowed})", name=f"ck_{table_name}_source")
