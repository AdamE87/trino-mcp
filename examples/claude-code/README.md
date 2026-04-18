# Claude Code: Opus root + Haiku Trino sub-agent

This directory is a drop-in Claude Code configuration that pairs a powerful
Opus root agent with a narrow, cheap Haiku sub-agent whose only capability
is querying Trino via [`trino-mcp`](../..).

```
┌──────────────────────────────────────┐
│  Root session (Opus)                 │
│  general reasoning, file edits, etc. │
└───────────────┬──────────────────────┘
                │  Agent(subagent_type="trino-query", ...)
                ▼
       ┌────────────────────────┐        mcp__trino__*
       │  trino-query (Haiku)   │  ─────────────────────▶  trino-mcp  ──▶  Trino
       │  Trino tools only      │                          (read-only)
       └────────────────────────┘
```

## Why split it this way

- **Cost.** Schema exploration and SQL drafting don't need Opus-level
  reasoning. Haiku handles the `list_catalogs → list_schemas →
  list_tables → describe_table → execute_query` loop at a fraction of
  the price.
- **Context hygiene.** Large `describe_table` and query results stay in
  the sub-agent's context; only the synthesized answer comes back to the
  root session.
- **Safety.** The sub-agent's `tools:` allowlist is restricted to the
  seven `mcp__trino__*` tools — no Bash, Edit, Write, or WebFetch. With
  the server's read-only SQL validator and a least-privilege Trino user,
  that's three defense layers before a write ever reaches the cluster.

## Files

| Path                                    | Purpose                                                                 |
| --------------------------------------- | ----------------------------------------------------------------------- |
| `.claude/agents/trino-query.md`         | Haiku sub-agent: frontmatter sets the model and tool allowlist; the body is its system prompt. |
| `CLAUDE.md`                             | Project memory that tells the root Opus agent to delegate all Trino questions to `trino-query` rather than calling the MCP tools itself. |
| `mcp.json`                              | Template MCP-server registration. Rename to `.mcp.json` at your project root to enable auto-loading. The filename omits the leading dot here so Claude Code does **not** auto-load the template if someone opens this example directory directly. |

## Adopting it in your own project

1. **Build the server image** from the repo root:
   ```bash
   docker build -t trino-mcp:latest .
   ```

2. **Copy the config into your project root:**
   ```bash
   cp -r examples/claude-code/.claude   ~/path/to/your-project/
   cp    examples/claude-code/CLAUDE.md ~/path/to/your-project/
   cp    examples/claude-code/mcp.json  ~/path/to/your-project/.mcp.json
   ```
   The rename from `mcp.json` → `.mcp.json` is what flips the file from
   "template" to "auto-loaded by Claude Code."

3. **Edit `.mcp.json`** with your cluster's hostname/port/catalog/schema.
   Leave `TRINO_USER` / `TRINO_PASSWORD` as `${TRINO_USER}` /
   `${TRINO_PASSWORD}` — they're forwarded from your shell so secrets
   stay out of the file.

4. **Export credentials** before starting Claude Code:
   ```bash
   export TRINO_USER="readonly-bot"
   export TRINO_PASSWORD="$(op read op://Eng/Trino/password)"   # or equivalent
   ```

5. **Open your project in Claude Code on Opus** and ask a data question.

## Verifying it works

Ask:

> What catalogs are available in Trino?

Expected behavior:

- The root Opus session calls `Agent(subagent_type="trino-query", ...)`
  rather than calling `mcp__trino__list_catalogs` itself.
- The sub-agent invokes `mcp__trino__list_catalogs` and returns a short
  list (e.g. `system`, `tpch`, plus whatever you've configured).

Negative checks — these should all fail safely:

- **Write attempt:** "Drop the `foo` table." The sub-agent has no write
  tools; even if it tried, `trino-mcp`'s SQL validator would reject any
  non-read statement, and a least-privilege `TRINO_USER` would reject it
  again at the cluster.
- **Non-Trino tool:** "Read `/etc/passwd`." The sub-agent's allowlist
  doesn't include `Read`/`Bash`/`WebFetch`, so the request has no tool
  to dispatch to.

## Local development

The repo root ships a `docker-compose.yml` with a Trino coordinator. To
smoke-test end-to-end against it:

```bash
docker compose up -d trino
docker build -t trino-mcp:latest .
# in your project: point TRINO_HOST at localhost:8080, no auth needed
export TRINO_HOST=localhost TRINO_PORT=8080 TRINO_USER=trino-mcp
claude  # open Claude Code on Opus
```

## See also

- [`../../README.md`](../../README.md) — `trino-mcp` server docs, env
  vars, and the read-only guarantees.
- [`../mcp.json`](../mcp.json) — the generic MCP-client template used
  when you're not running the sub-agent pattern.
