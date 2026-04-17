# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip wheel --wheel-dir /build/wheels .


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create a non-root user for the server.
RUN groupadd --system --gid 1000 trino && \
    useradd --system --uid 1000 --gid trino --home /home/trino --create-home trino

COPY --from=builder /build/wheels /wheels
RUN pip install --no-index --find-links=/wheels trino-mcp && \
    rm -rf /wheels

USER trino
WORKDIR /home/trino

# The MCP server speaks JSON-RPC over stdio; no port needs to be exposed.
ENTRYPOINT ["trino-mcp"]
