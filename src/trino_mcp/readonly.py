"""SQL read-only validation.

This module is a defense-in-depth layer on top of the user-side Trino
permissions. The authoritative read-only guarantee should come from the
Trino user's privileges; this module exists to block obvious mistakes and
surface a clear error message before a statement is sent to the server.
"""

from __future__ import annotations

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DDL, DML

ALLOWED_STATEMENT_TYPES: frozenset[str] = frozenset(
    {
        "SELECT",
        "SHOW",
        "DESCRIBE",
        "DESC",
        "EXPLAIN",
        "WITH",
        "VALUES",
        "USE",
    }
)

FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "TRUNCATE",
        "CREATE",
        "ALTER",
        "DROP",
        "GRANT",
        "REVOKE",
        "COMMENT",
        "CALL",
        "SET",
        "RESET",
        "START",
        "COMMIT",
        "ROLLBACK",
        "PREPARE",
        "EXECUTE",
        "DEALLOCATE",
        "REFRESH",
        "ANALYZE",
        "DENY",
    }
)


class ReadOnlyViolation(ValueError):
    """Raised when a query is not read-only."""


def _first_keyword(statement: Statement) -> str | None:
    for token in statement.flatten():
        if token.is_whitespace or token.ttype in (
            sqlparse.tokens.Comment,
            sqlparse.tokens.Comment.Single,
            sqlparse.tokens.Comment.Multiline,
        ):
            continue
        value = token.value.upper()
        if token.ttype in (Keyword, DML, DDL) or value in ALLOWED_STATEMENT_TYPES:
            return value
        # Stop at the first non-whitespace, non-comment token we see so we
        # don't skip past the leading keyword into an expression.
        return value
    return None


def validate_read_only(sql: str) -> str:
    """Validate that ``sql`` contains a single read-only statement.

    Returns the cleaned SQL (with trailing semicolons removed) on success.
    Raises :class:`ReadOnlyViolation` otherwise.
    """
    if not sql or not sql.strip():
        raise ReadOnlyViolation("Query must not be empty.")

    parsed = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if not parsed:
        raise ReadOnlyViolation("Query must not be empty.")
    if len(parsed) > 1:
        raise ReadOnlyViolation(
            "Only a single statement per request is allowed."
        )

    statement = parsed[0]
    leading = _first_keyword(statement)
    if leading is None:
        raise ReadOnlyViolation("Could not determine statement type.")
    if leading not in ALLOWED_STATEMENT_TYPES:
        raise ReadOnlyViolation(
            f"Statement '{leading}' is not allowed. Only read-only "
            f"statements are permitted: "
            f"{', '.join(sorted(ALLOWED_STATEMENT_TYPES))}."
        )

    for token in statement.flatten():
        if token.ttype in (DDL, DML):
            value = token.value.upper()
            if value in FORBIDDEN_KEYWORDS:
                raise ReadOnlyViolation(
                    f"Statement contains forbidden keyword '{value}'."
                )
        elif token.ttype is Keyword:
            value = token.value.upper()
            if value == "INTO" and leading == "SELECT":
                # SELECT ... INTO writes to a table in some dialects.
                raise ReadOnlyViolation(
                    "SELECT ... INTO is not allowed."
                )

    return str(statement).strip().rstrip(";").strip()
