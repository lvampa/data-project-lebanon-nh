"""Raw text moved out of Postgres into the archive before its columns are dropped.

The copy script and the migration that drops the columns both use these, so they
agree on where each value goes and how to find it again.
"""

from pymongo.collection import Collection

# One version per PDF, keyed by its canonical URL: the text pypdf extracted.
PDF_TEXT_SOURCE = "police_log_text"
# One version per entry, keyed by case number: its text and reason-action line.
ENTRY_TEXT_SOURCE = "police_log_entry_text"


def archived_keys(collection: Collection, source: str) -> set[str]:
    return set(collection.distinct("source_key", {"source": source}))
