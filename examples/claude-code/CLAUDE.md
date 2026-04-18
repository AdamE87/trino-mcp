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

## Briefing the sub-agent

The sub-agent cannot see this conversation. It sees only its own system
prompt and the `prompt` field you pass to the `Agent` tool — so that
brief must be self-contained. Specifically, forward any context it
needs to do the job:

- The actual question, in full (don't paraphrase down to a keyword).
- Any catalog / schema / table the user has already named or that you've
  inferred from earlier turns.
- Time ranges, filters, or definitions the user established earlier
  (e.g. "by 'active user' they mean `last_seen_at > now() - 30d`").
- The shape of answer you want back (a count, a top-10 table, a single
  row, a yes/no).

If the user's question is ambiguous, resolve the ambiguity with them
before delegating — the sub-agent has no way to ask clarifying
questions back. Treat its answer as authoritative for data questions.
