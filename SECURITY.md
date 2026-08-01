# Security Policy

## Scope

Continuum is a hackathon technology demonstration. **All incident, alert, and remediation data is
synthetic** (ADR [005](docs/adr/005-synthetic-incident-data.md)) — there is no real production
system, customer data, or PII in this repository at any point, including in seed data, code
comments, test fixtures, and captured evidence.

## Supported versions

| Version | Supported |
| --- | --- |
| `main` / latest release | Yes — fixes land here |
| Older tags | No — pinned snapshots for judging reproducibility |

## Secrets handling

- `.env` is gitignored; only `.env.example` (placeholder values) is committed.
- CockroachDB and AWS credentials are never hardcoded — loaded via environment variables only
  (`config.py`). `config.Settings` deliberately tolerates unknown env vars (`extra="ignore"`) so it
  coexists with the AWS SDK reading its own credentials from the environment.
- Deployment secrets live in the platform, not the repo: `COCKROACH_DATABASE_URL` and
  `COCKROACH_MCP_API_KEY` as Hugging Face Space repository secrets; SAM parameters (`NoEcho: true`)
  for the Lambda.
- CI runs on deliberately fake credentials — every outbound call in the unit suite is mocked at the
  import boundary, so a real key is never needed to make the suite pass.
- The `.mcp.json` MCP server config uses `${COCKROACH_MCP_API_KEY}` environment expansion, so no
  secret is committed even though the config is.

## Least privilege

- **The Managed MCP Server is used in read-only mode** (ADR [003](docs/adr/003-mcp-readonly-queries.md)).
  No write-capable MCP credentials are used or stored.
- **`agents/memory_agent.py` is the only module permitted to write** incident or remediation state.
  A single write path is a security property as much as an architectural one — the blast radius of
  a bug in any other agent is bounded to reads.
- The IAM credentials the application runs with are scoped to Bedrock model invocation only. They
  cannot list, create, or delete AWS resources; administrative work uses a separate profile.
- Cost guardrails are in place with a hard IAM deny-all action at the budget ceiling — see
  [`submission/COSTS.md`](submission/COSTS.md).

## Transport security

Database connections use `sslmode=require`, which encrypts without needing a CA file and works
unconditionally in Lambda's execution environment. This is an accepted trade-off for synthetic data
(ADR 005). `sslmode=verify-full&sslrootcert=system` is **not** a working substitute here — libpq's
`system` CA store is empty or unresolved on many platforms and fails with `certificate verify
failed`. For real certificate verification, ship the cluster CA file and point `&sslrootcert=` at it.

## Reporting a vulnerability

Please open a **private security advisory** on GitHub rather than a public issue:
[Security → Advisories → Report a vulnerability](https://github.com/iarjunganesh/continuum/security/advisories/new).

This is a solo hackathon project without a dedicated security team — response is best-effort, but
credential exposure or an injection vector in the demo API will be treated as urgent.

Please include: what you found, how to reproduce it, and the commit or release tag you observed it
on.

## Known limitations (by design — ADR [006](docs/adr/006-scope-cuts.md))

These are deliberate scope decisions for a demonstration project, documented rather than hidden:

- **No authentication on the demo API.** `api/main.py` is intended for local and demo use, not
  hardened for public production traffic. It is not internet-exposed by the reference deployment.
- **No custom RBAC layer** beyond the MCP Server's default read-only posture.
- **No rate limiting** on `POST /api/v1/alert`. Load characterisation deliberately exercises the
  read path only — see [`tests/load/k6_smoke.js`](tests/load/k6_smoke.js).
- **No audit trail of *who* triggered an incident** — the system records what happened, not who
  asked for it. Real deployment would need actor attribution on every state transition.
- **Prompt injection is not defended against.** Alert text flows into the reasoning prompt
  (`prompts/remediation_agent.txt`). Since alerts are synthetic and operator-authored here, this is
  out of scope — but ingesting untrusted alert sources would make it a live concern, and the
  proposed action is not sandboxed before being recorded.
