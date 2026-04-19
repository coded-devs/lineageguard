# LineageGuard — Project Memory

You are helping build **LineageGuard**, a developer tool for the
OpenMetadata "Back to the Metadata" hackathon (WeMakeDevs × OpenMetadata,
April 17–26, 2026).

## What LineageGuard Does

Takes a simulated schema change (e.g., "drop column `revenue_cents` from
table `raw_stripe_data`"), queries a local OpenMetadata server to walk
downstream lineage, fetches governance signals (tier, owner, glossary
terms, data contracts) for each downstream entity, runs a deterministic
ranking algorithm to classify impact severity (CRITICAL / HIGH / WARNING
/ INFO), and emits structured JSON findings. The tool is exposed as both
a CLI and a Model Context Protocol (MCP) server so AI assistants like
Claude Desktop and Cursor can invoke it.

## The Core Principle (Never Violate This)

**The engine is deterministic. The LLM is only a narrator.**

- All severity classification, lineage traversal, and impact decisions
  happen in pure Python code — no LLM calls inside the engine.
- LLMs (Claude, etc.) only consume the structured JSON output and
  translate it into human-readable explanations.
- If you find yourself tempted to add "ask an LLM to decide…" anywhere
  in the engine, stop and refuse. This is the project's architectural
  thesis and must not be compromised.

## Tech Stack

- **Language:** Python 3.11
- **HTTP client:** `httpx` (NOT `requests`)
- **Data validation:** `pydantic` v2
- **CLI framework:** `click`
- **MCP framework:** Official `mcp` Python SDK (stdio transport)
- **Testing:** `pytest`
- **OpenMetadata:** Runs locally via Docker Compose, version 1.12+ stable

## Build Order (Enforce Strictly)

1. Environment + Docker OpenMetadata running
2. Seed script that creates demo metadata idempotently
3. OpenMetadata REST API client wrapper
4. Lineage walker
5. Governance signal fetcher
6. Semantic ranker (4-level)
7. Output formatter (JSON + Markdown)
8. CLI tool
9. MCP server
10. Demo video

Do not skip steps. Do not merge steps. The user is a beginner and needs
each step small and verifiable.

## Directory Structure (Target)
lineageguard/
├── README.md
├── CLAUDE.md                   # Read this file
├── .gitignore
├── .env.example
├── pyproject.toml
├── docker-compose.yml          # OpenMetadata deployment
├── seed.py                     # idempotent demo seeder
├── src/lineageguard/
│   ├── init.py
│   ├── client.py               # OpenMetadata REST client
│   ├── models.py               # Pydantic schemas
│   ├── lineage.py              # downstream lineage walker
│   ├── governance.py           # tier / owner / glossary / contract fetcher
│   ├── ranker.py               # deterministic severity logic
│   ├── engine.py               # orchestration
│   ├── formatter.py            # JSON + Markdown output
│   ├── cli.py                  # Click CLI
│   └── mcp_server.py           # MCP server entrypoint
├── tests/
│   └── test_ranker.py
└── examples/
├── sample_change_spec.json
└── sample_output.json

## Coding Conventions

- **Beginner-friendly.** The user does not write Python daily. Every
  function needs a clear docstring. Avoid clever one-liners, dense
  comprehensions, or "pythonic" tricks. Prefer explicit loops and
  named variables.
- **Type hints on every function.** Full signatures.
- **Fail loud and clear.** When something goes wrong, print a helpful
  error message. Never swallow exceptions silently.
- **No premature abstraction.** No base classes, no plugin systems, no
  decorators unless strictly needed.
- **Print, don't log.** For a demo tool, `print()` with clear prefixes
  (`[INFO]`, `[ERROR]`) is fine. Skip the `logging` module.
- **One module, one responsibility.** Don't mix lineage walking and
  ranking in the same file.
- **All secrets via environment variables.** Never hardcode PATs,
  API keys, or URLs. Use a `.env` file + `python-dotenv`.

## OpenMetadata Connection

- Local URL: `http://localhost:8585`
- API base: `http://localhost:8585/api/v1`
- Authentication: Personal Access Token (PAT) as Bearer token
- Environment variables (in `.env`):
  - `OPENMETADATA_URL=http://localhost:8585/api/v1`
  - `OPENMETADATA_TOKEN=<paste PAT here>`

## The Canonical Demo Scenario

The seed script must create exactly this graph:

raw_stripe_data (Table, Stripe service, no tier)
└─ lineage ─▶ stg_stripe_charges (Table, dbt/Snowflake)
└─ lineage ─▶ fct_orders (Table, Tier 1, Finance owner,
│                 linked to glossary term "Net Revenue",
│                 data contract "Finance Core Metrics")
│     └─ lineage ─▶ Executive Revenue Dashboard
│                     (Dashboard, Metabase, Tier 1)
└─ lineage ─▶ marketing_attribution_dashboard
(Dashboard, Tier 3, no governance)
Parallel branch (depth-2):
raw_stripe_data ─▶ dim_customers (Table, Tier 2,
linked to glossary term "Customer")

Running the canonical demo (`drop_column revenue_cents on
raw_stripe_data`) must produce at least one CRITICAL finding (fct_orders
+ Executive Dashboard), one HIGH, and one INFO. This variety is
essential for the demo to land.

## Non-Negotiables

1. Engine is deterministic. LLM is narrator only.
2. Seed script is idempotent (safe to re-run any number of times).
3. All API calls have timeouts (10s default).
4. All Pydantic models have strict typing.
5. Every feature ships with a way to verify it works from the terminal.
6. No feature creep. If it's not in the build order above, it's out of scope.

## When the User Asks for Code

- Generate the complete file contents, not fragments.
- Include imports at the top.
- Add a `__main__` block to files that can be run standalone,
  so the user can test each module in isolation.
- After generating code, tell the user exactly what command to run
  to verify it works.

## When Generating Error Messages

Error messages must:
- Name the function that failed
- Include the value that caused the problem
- Suggest the likely fix

Example: `[ERROR] fetch_entity(): Entity 'raw_stripe_data' not found
at http://localhost:8585/api/v1/tables/name/raw_stripe_data. Did you
run seed.py?`
