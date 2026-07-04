# Security Policy

## Scope
Continuum is a hackathon technology demonstration. All incident, alert, and remediation data is synthetic (see `docs/adr/005-synthetic-incident-data.md`) — there is no real production system, customer data, or PII in this repository at any point.

## Secrets handling
- `.env` is gitignored; only `.env.example` (placeholder values) is committed
- CockroachDB credentials and AWS credentials are never hardcoded — loaded via environment variables only (`config.py`)
- The CockroachDB Cloud Managed MCP Server is used in **read-only mode** for this project (see ADR 003) — no write-capable MCP credentials are used or stored

## Reporting a vulnerability
If you find a security issue in this repo (e.g., a credential accidentally committed, an injection vector in the demo API), please open a private security advisory on GitHub rather than a public issue. This is a hackathon project without a dedicated security team, so response times are best-effort.

## Known limitations (by design, see ADR 006)
- No custom RBAC layer beyond MCP Server's default safe/read-only posture
- Demo API (`api/main.py`) is intended for local/demo use, not hardened for public production traffic
