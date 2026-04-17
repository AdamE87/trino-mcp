"""Thin wrapper around the Trino DB-API client."""

from __future__ import annotations

import logging
from typing import Any

from trino.auth import BasicAuthentication
from trino.dbapi import Connection, connect

from trino_mcp.config import TrinoConfig

logger = logging.getLogger(__name__)


def quote_identifier(identifier: str) -> str:
    """Quote a Trino identifier for safe interpolation in SHOW/DESCRIBE."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Identifier must be a non-empty string.")
    return '"' + identifier.replace('"', '""') + '"'


class TrinoClient:
    def __init__(self, config: TrinoConfig) -> None:
        self._config = config
        self._connection: Connection | None = None

    @property
    def config(self) -> TrinoConfig:
        return self._config

    def _build_connection(self) -> Connection:
        cfg = self._config
        auth = (
            BasicAuthentication(cfg.user, cfg.password)
            if cfg.password is not None
            else None
        )
        verify: bool | str = cfg.verify_ssl
        logger.info(
            "Connecting to Trino at %s://%s:%s as %s",
            cfg.http_scheme,
            cfg.host,
            cfg.port,
            cfg.user,
        )
        return connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            catalog=cfg.catalog,
            schema=cfg.schema,
            http_scheme=cfg.http_scheme,
            auth=auth,
            source=cfg.source,
            verify=verify,
            request_timeout=cfg.request_timeout,
        )

    def connection(self) -> Connection:
        if self._connection is None:
            self._connection = self._build_connection()
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:  # noqa: BLE001
                logger.exception("Error while closing Trino connection")
            finally:
                self._connection = None

    def run_query(
        self,
        sql: str,
        *,
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Execute ``sql`` and return a dict with columns and rows.

        The caller is responsible for making sure the statement is read-only.
        """
        limit = max_rows if max_rows is not None else self._config.max_rows
        if limit <= 0:
            raise ValueError("max_rows must be positive.")

        conn = self.connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            rows: list[list[Any]] = []
            truncated = False
            while len(rows) < limit:
                batch = cursor.fetchmany(min(limit - len(rows), 1000))
                if not batch:
                    break
                rows.extend(list(r) for r in batch)
            # Check whether more rows would have been available.
            extra = cursor.fetchone()
            if extra is not None:
                truncated = True

            columns = (
                [
                    {"name": col[0], "type": col[1]}
                    for col in (cursor.description or [])
                ]
                if cursor.description
                else []
            )
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
                "query_id": getattr(cursor, "query_id", None),
            }
        finally:
            try:
                cursor.close()
            except Exception:  # noqa: BLE001
                logger.exception("Error while closing Trino cursor")
