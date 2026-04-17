"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TrinoConfig:
    host: str
    port: int
    user: str
    password: str | None
    catalog: str | None
    schema: str | None
    http_scheme: str
    verify_ssl: bool
    source: str
    max_rows: int
    request_timeout: float

    @classmethod
    def from_env(cls) -> "TrinoConfig":
        password = os.getenv("TRINO_PASSWORD") or None
        default_scheme = "https" if password else "http"
        scheme = os.getenv("TRINO_HTTP_SCHEME", default_scheme).lower()
        if scheme not in {"http", "https"}:
            raise ValueError(
                f"TRINO_HTTP_SCHEME must be 'http' or 'https', got {scheme!r}"
            )
        verify = os.getenv("TRINO_VERIFY_SSL", "true").lower() not in {
            "0",
            "false",
            "no",
        }
        return cls(
            host=os.getenv("TRINO_HOST", "localhost"),
            port=int(os.getenv("TRINO_PORT", "8080")),
            user=os.getenv("TRINO_USER", "trino-mcp"),
            password=password,
            catalog=os.getenv("TRINO_CATALOG") or None,
            schema=os.getenv("TRINO_SCHEMA") or None,
            http_scheme=scheme,
            verify_ssl=verify,
            source=os.getenv("TRINO_SOURCE", "trino-mcp"),
            max_rows=int(os.getenv("TRINO_MAX_ROWS", "1000")),
            request_timeout=float(os.getenv("TRINO_REQUEST_TIMEOUT", "60")),
        )
