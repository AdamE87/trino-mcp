# Project instructions

This project has a dedicated Trino sub-agent. **For any question that
requires data from Trino — listing catalogs/schemas/tables, describing a
table, running SQL, or fetching stats — delegate to the `trino-query`
sub-agent via the `Agent` tool.** Do not call the `mcp__trino__*` tools
from the root session.

Why:

- The sub-agent runs on a cheaper model (Haiku) with a narrow system
  prompt tuned for schema exploration and read-only SQL.
- Keeping Trino tool calls out of the root session protects its context
  window from large query results and schema listings.
- The sub-agent's tool allowlist makes it impossible for it to do
  anything other than query Trino, which is a useful safety property.

When delegating, pass the user's question through unchanged unless you
need to add constraints (e.g. "only the `prod` catalog"). Treat the
sub-agent's answer as authoritative for data questions.
