import re

from sqlalchemy.dialects import postgresql


def compile_pg(stmt):
    return stmt.compile(dialect=postgresql.dialect())


def executed_stmt(mock_db):
    return mock_db.execute.call_args.args[0]


def upsert_set_columns(stmt) -> set[str]:
    sql = str(compile_pg(stmt))
    set_clause = sql.split("DO UPDATE SET", 1)[1].split(" RETURNING", 1)[0]
    return set(re.findall(r"(\w+) = ", set_clause))
