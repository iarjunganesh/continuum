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
- **The CI deploy holds two GitHub repository secrets** (ADR [010](docs/adr/010-deploy-on-tag-from-ci.md)):
  `AWS_DEPLOY_ROLE_ARN` and `COCKROACH_DATABASE_URL`. The second is a live cluster credential in a
  third party, on a public repository, and is stated here rather than left to be discovered.
  Repository secrets are encrypted and are never exposed to workflows triggered by forked pull
  requests, and `deploy.yml` runs only on tags, which only a maintainer can push. The cluster holds
  synthetic data only (ADR 005), so the credential is not a route to anything real. The honest
  alternative — resolving the DSN from an AWS-side secret store at runtime — is the right move if
  that ever stops being true.
- **No long-lived AWS keys exist in GitHub.** The deploy workflow assumes an IAM role through
  GitHub's OIDC provider, so credentials are minted per run and expire with it. The role's trust
  policy is scoped to this repository **and** to `refs/tags/*`, so a branch push cannot assume it
  even if a future workflow tries. Its permissions are broader than ideal — SAM creates the
  function's execution role as part of the stack, so `iam:*` is currently attached; narrowing it to
  this stack's role paths is recorded as outstanding in ADR 010 rather than glossed over.
- CI runs on deliberately fake credentials — every outbound call in the unit suite is mocked at the
  import boundary, so a real key is never needed to make the suite pass.
- **Secrets must not reach a terminal either.** Gitignoring `.env` and keeping the DSN out of
  `samconfig.toml` stops a credential reaching the repository; neither stops one reaching stdout,
  where it lands in scrollback and in any transcript later shared for help. The realistic failure
  is not printing a password deliberately but running a **broad read of a store that contains
  one** — `aws lambda get-function-configuration --query "Environment.Variables"` returns this
  function's whole environment, including the live database URL. Query the single field instead.
  The rule and its worked examples are in `CLAUDE.md` under Non-negotiable constraints, so agents
  working in this repo inherit it.

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
