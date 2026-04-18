# trino-mcp

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server
for [Trino](https://trino.io), built on top of the official
[`trino` Python client](https://github.com/trinodb/trino-python-client).

The server exposes a small set of MCP tools so an LLM can inspect catalogs,
schemas, tables, and run read-only SQL against Trino. Any statement that
would write or modify state is rejected before it reaches the cluster.

## Features

- `execute_query` — run a single read-only statement (`SELECT`, `SHOW`,
  `DESCRIBE`, `EXPLAIN`, `WITH`, `VALUES`, `USE`). Results are capped at
  `TRINO_MAX_ROWS` and include a `truncated` flag.
- `list_catalogs`, `list_schemas`, `list_tables`
- `describe_table`, `show_create_table`, `show_stats`
- Read-only enforcement via SQL parsing **and** a recommended least-privilege
  Trino user. Defense in depth: the server rejects obvious writes, while
  Trino's own access controls are the authoritative guarantee.

## Configuration

All configuration is via environment variables:

| Variable               | Default        | Notes                                          |
| ---------------------- | -------------- | ---------------------------------------------- |
| `TRINO_HOST`           | `localhost`    | Coordinator hostname                           |
| `TRINO_PORT`           | `8080`         |                                                |
| `TRINO_USER`           | `trino-mcp`    | Use a dedicated read-only Trino user           |
| `TRINO_PASSWORD`       | _(unset)_      | If set, Basic auth is used                     |
| `TRINO_HTTP_SCHEME`    | `http`/`https` | Defaults to `https` when a password is set     |
| `TRINO_VERIFY_SSL`     | `true`         | Set to `false` to disable TLS verification     |
| `TRINO_CATALOG`        | _(unset)_      | Default catalog for queries                    |
| `TRINO_SCHEMA`         | _(unset)_      | Default schema for queries                     |
| `TRINO_SOURCE`         | `trino-mcp`    | Value reported to Trino for query attribution  |
| `TRINO_MAX_ROWS`       | `1000`         | Row cap per query                              |
| `TRINO_REQUEST_TIMEOUT`| `60`           | Seconds                                        |

## Run with Docker

Build the image:

```bash
docker build -t trino-mcp:latest .
```

The server speaks MCP over stdio, so your MCP client launches a container on
demand with `docker run -i --rm ...`.

### `mcp.json` with credentials from the host environment

Credentials live on the host and are **forwarded into the container at launch
time** — they are never written into `mcp.json` or baked into the image.

The trick is `docker run -e VAR` (no `=value`): when the value is omitted,
Docker reads the variable from the process that launched it, which is the
MCP client. Combine that with an `env` block in `mcp.json` that pulls from
the shell running the client, and secrets stay in your host's secret store.

```json
{
  "mcpServers": {
    "trino": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "TRINO_HOST",
        "-e", "TRINO_PORT",
        "-e", "TRINO_HTTP_SCHEME",
        "-e", "TRINO_USER",
        "-e", "TRINO_PASSWORD",
        "-e", "TRINO_CATALOG",
        "-e", "TRINO_SCHEMA",
        "-e", "TRINO_MAX_ROWS",
        "trino-mcp:latest"
      ],
      "env": {
        "TRINO_HOST": "trino.example.com",
        "TRINO_PORT": "443",
        "TRINO_HTTP_SCHEME": "https",
        "TRINO_USER": "${TRINO_USER}",
        "TRINO_PASSWORD": "${TRINO_PASSWORD}",
        "TRINO_CATALOG": "hive",
        "TRINO_SCHEMA": "default",
        "TRINO_MAX_ROWS": "1000"
      }
    }
  }
}
```

How it flows:

1. Your shell (or secret manager) exports `TRINO_USER` and `TRINO_PASSWORD`.
2. The MCP client inherits those, and the `env` block in `mcp.json` keeps
   them set when it spawns `docker`.
3. `docker run -e TRINO_USER -e TRINO_PASSWORD` copies the values from
   that process into the container, where the server reads them.

Ways to load the host-side variables before starting the MCP client:

```bash
# Option A: export from your shell profile / direnv / 1Password CLI
export TRINO_USER="readonly-bot"
export TRINO_PASSWORD="$(op read op://Eng/Trino/password)"

# Option B: per-launch env file
set -a; source ~/.config/trino-mcp.env; set +a
```

Or, let Docker load an env file directly, skipping the client shell:

```json
{
  "mcpServers": {
    "trino": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--env-file", "/etc/trino-mcp/credentials.env",
        "-e", "TRINO_HOST=trino.example.com",
        "-e", "TRINO_PORT=443",
        "-e", "TRINO_HTTP_SCHEME=https",
        "trino-mcp:latest"
      ]
    }
  }
}
```

Make sure that file is only readable by your user
(`chmod 600 credentials.env`).

Other notes:

- `-i` is required — MCP clients communicate with the server over stdio.
- To talk to a Trino running on the host from inside the container, use
  `--network=host` on Linux or set `TRINO_HOST=host.docker.internal` on
  Docker Desktop (macOS / Windows).
- Do **not** hard-code `TRINO_PASSWORD` into `mcp.json` or pass it as
  `-e TRINO_PASSWORD=...` on the command line — both leak the secret into
  logs and process listings.

A fuller example lives in [`examples/mcp.json`](examples/mcp.json).

### Using with Claude Code (delegated Haiku sub-agent)

[`examples/claude-code/`](examples/claude-code/) is a drop-in
configuration that pairs your Claude Code root session (Opus or Sonnet —
both work) with a narrow Haiku sub-agent whose only tools are
`mcp__trino__*`. The root delegates data questions to the sub-agent,
keeping query results out of its context and schema exploration off the
larger model. See that directory's README for the architecture and
copy-in instructions.

### Local Trino for development

A `docker-compose.yml` is included that runs a Trino coordinator and builds
the `trino-mcp` image. Typical workflow:

```bash
docker compose up -d trino
docker compose build trino-mcp
```

Then point your MCP client at `trino-mcp:latest` as shown above.

## Run without Docker

```bash
pip install .
TRINO_HOST=localhost TRINO_PORT=8080 trino-mcp
```

Corresponding `mcp.json`:

```json
{
  "mcpServers": {
    "trino": {
      "command": "trino-mcp",
      "env": {
        "TRINO_HOST": "localhost",
        "TRINO_PORT": "8080",
        "TRINO_USER": "trino-mcp"
      }
    }
  }
}
```

## Read-only guarantees

The server applies two layers of protection:

1. **Statement validation.** Every query is parsed with `sqlparse`. Only a
   fixed list of read-only leading keywords is accepted; multi-statement
   requests, `INSERT`/`UPDATE`/`DELETE`/`MERGE`, DDL, and `CALL` are rejected.
2. **Least-privilege user.** The validator catches mistakes, but the
   authoritative guarantee must come from Trino itself. Create a user that
   only has `SELECT` privileges on the catalogs you want exposed (or use a
   catalog with a read-only connector) and set `TRINO_USER` / `TRINO_PASSWORD`
   accordingly.

## Development

```bash
pip install -e ".[dev]"
pytest
```
