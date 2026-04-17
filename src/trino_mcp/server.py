"""MCP server exposing read-only access to a Trino cluster."""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from trino_mcp.client import TrinoClient, quote_identifier
from trino_mcp.config import TrinoConfig
from trino_mcp.readonly import ReadOnlyViolation, validate_read_only

logger = logging.getLogger(__name__)


SERVER_INSTRUCTIONS = """\
This MCP server provides **read-only** access to a Trino cluster.

Use the tools to list catalogs, schemas, and tables, describe a table's
columns, and run read-only SQL queries (SELECT, SHOW, DESCRIBE, EXPLAIN,
WITH, VALUES). Any statement that would write or modify state will be
rejected before it is sent to Trino.

For best results, pair this server with a Trino user that has only the
privileges it needs. The server cannot override the Trino catalog's own
access controls.
"""


mcp = FastMCP("trino-mcp", instructions=SERVER_INSTRUCTIONS)

_client: TrinoClient | None = None


def get_client() -> TrinoClient:
    global _client
    if _client is None:
        _client = TrinoClient(TrinoConfig.from_env())
    return _client


def set_client(client: TrinoClient | None) -> None:
    """Override the client (primarily for tests)."""
    global _client
    if _client is not None and _client is not client:
        _client.close()
    _client = client


def _run(sql: str, *, max_rows: int | None = None) -> dict[str, Any]:
    return get_client().run_query(sql, max_rows=max_rows)


@mcp.tool()
def execute_query(sql: str, max_rows: int | None = None) -> dict[str, Any]:
    """Execute a read-only SQL statement against Trino.

    Args:
        sql: A single read-only Trino SQL statement. Allowed leading
            keywords are SELECT, SHOW, DESCRIBE, EXPLAIN, WITH, VALUES,
            and USE. Anything else is rejected.
        max_rows: Maximum rows to return. Defaults to ``TRINO_MAX_ROWS``
            (1000). If the query produces more rows, the result is
            truncated and ``truncated`` is set to ``true``.

    Returns:
        A dict with ``columns`` (name and type), ``rows`` (list of
        lists), ``row_count``, ``truncated``, and ``query_id``.
    """
    try:
        cleaned = validate_read_only(sql)
    except ReadOnlyViolation as exc:
        raise ValueError(str(exc)) from exc
    return _run(cleaned, max_rows=max_rows)


@mcp.tool()
def list_catalogs() -> list[str]:
    """List all catalogs visible to the configured Trino user."""
    result = _run("SHOW CATALOGS")
    return [row[0] for row in result["rows"]]


@mcp.tool()
def list_schemas(catalog: str) -> list[str]:
    """List schemas in ``catalog``."""
    sql = f"SHOW SCHEMAS FROM {quote_identifier(catalog)}"
    result = _run(sql)
    return [row[0] for row in result["rows"]]


@mcp.tool()
def list_tables(catalog: str, schema: str) -> list[str]:
    """List tables and views in ``catalog.schema``."""
    sql = (
        f"SHOW TABLES FROM {quote_identifier(catalog)}."
        f"{quote_identifier(schema)}"
    )
    result = _run(sql)
    return [row[0] for row in result["rows"]]


@mcp.tool()
def describe_table(
    catalog: str, schema: str, table: str
) -> list[dict[str, Any]]:
    """Return column information for ``catalog.schema.table``.

    Each entry contains ``column``, ``type``, ``extra``, and ``comment``.
    """
    fq = (
        f"{quote_identifier(catalog)}."
        f"{quote_identifier(schema)}."
        f"{quote_identifier(table)}"
    )
    result = _run(f"DESCRIBE {fq}")
    out: list[dict[str, Any]] = []
    for row in result["rows"]:
        padded = list(row) + [None] * (4 - len(row))
        out.append(
            {
                "column": padded[0],
                "type": padded[1],
                "extra": padded[2],
                "comment": padded[3],
            }
        )
    return out


@mcp.tool()
def show_create_table(catalog: str, schema: str, table: str) -> str:
    """Return the ``SHOW CREATE TABLE`` DDL for the table (read-only)."""
    fq = (
        f"{quote_identifier(catalog)}."
        f"{quote_identifier(schema)}."
        f"{quote_identifier(table)}"
    )
    result = _run(f"SHOW CREATE TABLE {fq}")
    if not result["rows"]:
        return ""
    return result["rows"][0][0]


@mcp.tool()
def show_stats(catalog: str, schema: str, table: str) -> dict[str, Any]:
    """Return Trino's column statistics for ``catalog.schema.table``."""
    fq = (
        f"{quote_identifier(catalog)}."
        f"{quote_identifier(schema)}."
        f"{quote_identifier(table)}"
    )
    return _run(f"SHOW STATS FOR {fq}")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
