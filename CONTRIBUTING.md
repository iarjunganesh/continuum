# Contributing

This is a **solo hackathon submission** for the CockroachDB × AWS Hackathon 2026, built within the
official Submission Period (June 30 – August 18, 2026). External contributions during that window
won't be merged, to keep the submission's authorship unambiguous under the hackathon's
IP/originality rules.

After judging concludes this note will be updated and the project opened to normal contribution flow
(issues, PRs, discussion). Bug reports and questions are welcome any time — it's only *merges* that
are paused.

## Local development

```bash
git clone https://github.com/iarjunganesh/continuum.git
cd continuum

cp .env.example .env    # fill in COCKROACH_DATABASE_URL + AWS credentials
make install            # requires Python 3.14
make migrate
make seed-data          # or seed-data-offline — no AWS call needed
```

On Windows (PowerShell 7+, no `make`):

```powershell
git clone https://github.com/iarjunganesh/continuum.git
cd continuum

Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\scripts\migrate_and_seed.ps1        # -Offline for deterministic vectors, no AWS call
```

**The Makefile is the source of truth for how to run anything.** If a command in the README and the
Makefile disagree, the Makefile is right and the README needs fixing. On Windows, read the recipe
under the target you want — nearly every one is a single `python scripts/….py`.

## Quality gates

Everything CI enforces, runnable locally:

```bash
make lint         # ruff — also lints notebooks
make typecheck    # mypy
make test         # pytest tests/unit tests/integration
make coverage     # coverage report; CI gate is 90%, currently 100%
make check-drift  # docs vs repo: versions, counts, links, generated files
```

If your change adds a **screenshot** anywhere under `assets/`, also run
`python scripts/redact_evidence.py --check`. It fails on a capture with no entry in
`scripts/redact_evidence.py` — an empty region tuple is a valid entry and means "someone looked and
it needs nothing". A raw window capture carries the signed-in user's profile photograph, and on AWS
pages an account id.

On Windows (PowerShell 7+):

```powershell
ruff check . ; ruff format --check .          # make lint — both halves are CI-gated separately
mypy agents/ api/ observability/ config.py    # make typecheck
pytest tests/unit tests/integration -v        # make test
pytest tests/unit tests/integration --cov=agents --cov=api --cov=observability --cov-report=term-missing
```

`tests/integration` needs a live CockroachDB at `$COCKROACH_DATABASE_URL` and skips gracefully
without one — so locally, `make test` usually runs the unit suite only. CI provisions an ephemeral
single-node container so the integration suite actually executes on every push.

## Testing conventions

- One unit test file per agent/module.
- **Mock at the import boundary** (`patch("agents.x.boto3")`, `patch("agents.x.psycopg")`) — never
  mock the class under test. See `tests/unit/` for the established pattern per agent.
- Tests that assert the recovery contract are the ones that matter: recovery read before any write,
  each step inside an explicit `SERIALIZABLE` transaction, interrupted steps re-executed (never
  skipped, never duplicated), forward steps claimed exactly once under concurrency.

> A green unit suite is necessary but not sufficient for anything touching the MCP client or
> Bedrock. Both are mocked at the boundary, so the suite passes against a client that would fail
> against the real server. Changes there need a live round trip.

## Things that will get a change rejected

These are load-bearing invariants, not preferences. Each is documented in an ADR:

- **Writing to `incidents` or `remediation_steps` from anywhere except `agents/memory_agent.py`.**
  The single write path is load-bearing for ADR 001/003.
- **Caching incident state in process memory across invocations.** The orchestrator's first action
  must always be a CockroachDB read. In-memory caching would silently break the one guarantee this
  project exists to prove (ADR 002).
- **Collapsing the two-phase step checkpoint.** `checkpoint_step_start` commits `executing` *before*
  the execution window; `checkpoint_step_done` commits `executed` *after*. They must stay two
  separate transactions with the window between them — a kill has to land with `executing` durable
  (ADR 009).
- **Changing the forward-step claim from `ON CONFLICT DO NOTHING` to `DO UPDATE`.** That silently
  breaks exactly-once under concurrent invocations (ADR 009).
- **Making the Bedrock correlation call fatal.** It's wrapped in try/except deliberately so a
  Bedrock outage degrades to "no precedent" instead of aborting the incident before it's durable.
- **Introducing real company names, real infrastructure, or anything resembling real credentials**
  into seed data, comments, or docs (ADR 005).
- **Reintroducing `extra="forbid"` on `config.Settings`.** It breaks startup for anyone with
  ordinary AWS credentials exported.

## Style

- Python 3.14, psycopg 3, async where I/O-bound.
- structlog JSON logging (`observability/structured_logger.py`) — no bare `print`.
- Pydantic models for structured data crossing an agent boundary.
- Model prompts live in `prompts/` as data, not inline strings.
- ADRs go in `docs/adr/`, numbered sequentially, one decision per file.
- Commit subjects carry no version numbers — the tag and CHANGELOG carry the version.

**Pushing a `v*.*.*` tag deploys the orchestrator to AWS Lambda** ([ADR 010](docs/adr/010-deploy-on-tag-from-ci.md)),
so `git push --follow-tags` changes a live system, not just GitHub. Run every gate above first —
that is what the release checklist is now protecting. Pushes to `main` do not deploy, deliberately.

Keeping docs in sync with code is part of the change, not follow-up work. See the release &
repo-sync discipline section in [`CLAUDE.md`](CLAUDE.md) for the checklist.

## Before opening an issue

Check [`docs/adr/`](docs/adr/) — a number of "why isn't X included" questions are already answered
there as deliberate scope decisions rather than oversights. ADR 004 (ccloud CLI evaluated and cut)
and ADR 006 (explicit scope cuts) cover most of them.
