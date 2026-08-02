# Submission Checklist — CockroachDB × AWS Hackathon

Tracks directly against the [official rules](https://cockroachdb-ai.devpost.com/rules).
Hackathon facts, prizes, timeline, and judging-criteria mapping: [`DEVPOST.md`](DEVPOST.md).

**Deadline: August 18, 2026, 5:00 pm ET.** Update this file as each item completes — an unchecked
box here is the honest state, not an oversight.

---

## Eligibility / Build Constraints

- [x] **All code newly written during the Submission Period** (June 30 – Aug 18, 2026). No
      pre-existing code was incorporated from any prior project; enforced as a standing constraint
      in `CLAUDE.md`
- [x] **AI coding assistant usage disclosed** — Claude Code, stated in the README's
      "Disclosure & Disclaimer" section. The rules explicitly permit AI assistants
- [x] **All third-party data/APIs authorized** — synthetic data only (ADR 005). No real
      infrastructure, company names, customer data, or PII anywhere in the repo

## Required Project Requirements

- [x] **Uses CockroachDB as persistent memory layer, deployed on AWS** — *CockroachDB Cloud is
      live, and the orchestrator runs on AWS Lambda in eu-central-1 (deployed 2026-08-01). The
      recovery contract was observed on the deployed function: successive cold invocations drove
      one incident 0 → 1 → 2 → `resolved`, each resuming from CockroachDB with the same
      `incident_id`*
- [x] **≥2 CockroachDB tools meaningfully integrated** (not merely initialized):
  - [x] **Distributed Vector Indexing** — `incident_embeddings` `VECTOR(1024)` with a
        `service`-prefixed C-SPANN index; the Correlation Agent's live query filters and ANN-ranks
        in one round trip
  - [x] **CockroachDB Cloud Managed MCP Server** — `agents/query_agent.py` is the *application's*
        MCP client, called at runtime from `GET /api/v1/incidents/open` and the Gradio UI (ADR 003)
  - *ccloud CLI and the Agent Skills Repo — evaluated and deliberately not used (ADR 004); not
    claimed as additional tools*
- [x] **≥1 AWS service:**
  - [x] **Amazon Bedrock** — Titan Text Embeddings V2 + Claude Sonnet 4.5, verified end to end
        (2026-08-01) both locally and from the deployed Lambda. Every remediation step records
        `reasoning_source` / `correlation_source`, so "Bedrock actually ran" is checkable in the
        database rather than assumed — the deploy smoke test returned `bedrock` for both
  - [x] **AWS Lambda** — deployed from `infra/template.yaml` via SAM:
        `arn:aws:lambda:eu-central-1:504804196134:function:continuum-orchestrator`, stack
        `continuum`. No provisioned concurrency (ADR 002), so every invocation is a cold start —
        1.71 s init, 129 MB of a 512 MB allocation

## Submission Materials

- [x] **Public GitHub repo** with MIT `LICENSE`
  - [ ] License visible in the repo's **About** sidebar (GitHub must detect it — verify on the
        rendered repo page, not just that the file exists)
- [x] **README** with setup/run instructions, dependencies, and example config (`.env.example`)
- [ ] **Functional demo app URL**
  - [x] Deployed to Hugging Face Spaces (`docs/DEPLOY.md`) — free, cardless, auto-synced on push
  - [x] Space secrets `COCKROACH_DATABASE_URL` + `COCKROACH_MCP_CLUSTER_ID` set; Space builds
  - [ ] URL confirmed publicly accessible in a private/incognito window before submitting
  - [ ] Populated with seeded synthetic incidents. Not blocked by anything: `make seed-data-offline`
        seeds incidents + remediation history + deterministic vectors with **zero AWS calls**. Real
        Titan vectors can be captured once (`scripts/capture_seed_embeddings.py`) and seeded
        `--from-fixture`. Run against the Space's cluster, then check this
- [ ] **Demo video** (<3 min, public on YouTube/Vimeo) — script: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)
  - [ ] Shows the project functioning on its intended platform
  - [ ] Shows the CockroachDB memory layer at work — the kill-and-resume beat
  - [ ] Public, not unlisted
  - [ ] No third-party trademarks / unlicensed music
  - [ ] No credentials or account IDs in any frame
- [x] **Text description of features and functionality** — [`DEVPOST.md`](DEVPOST.md) +
      [`DEVPOST_README.md`](DEVPOST_README.md) (paste-ready mirror with absolute URLs)
- [x] **Explicit list: which CockroachDB tools used + how** — README § CockroachDB Tools Used,
      expanded in `DEVPOST.md`
- [x] **Explicit list: which AWS services used + how** — README § AWS Services Used
- [x] *Optional:* **architecture diagram** — two, in fact: components and the recovery sequence,
      both brand-themed renders in `assets/architecture/`
- [ ] *Optional:* feedback on CockroachDB AI tools/features

## Pre-Submission Sanity Checks

- [ ] Repo runs from a clean clone following only the README instructions
- [x] No secrets committed — `.env` gitignored, `.env.example` holds placeholders only, `.mcp.json`
      uses environment expansion
- [ ] Demo app accessible without login
- [ ] Video watched start to finish, verified under 3:00 on the **exported file**
- [x] All CI gates green: ruff lint, ruff format, mypy, Devpost mirror freshness, 57 unit +
      9 integration tests, 100% coverage against a 90% gate
- [x] No broken links repo-wide (markdown links and HTML `src`/`srcset`/`href`)
- [x] No placeholder artifacts shipping as finished — pending items are marked pending explicitly

---

## Known Gaps — stated plainly

These are real and unresolved as of `v0.9.0`. Listing them here is deliberate: a judge who finds
them unlisted reads the whole checklist as unreliable. This table is the **single** place open
gaps are tracked — `docs/DEMO_READINESS_CHECKLIST.md` previously duplicated it and was removed
once its findings were either closed with evidence or folded in here, because two gap lists
drift and the stale one is always the one a judge reads.

| Gap | Impact | Status |
| --- | --- | --- |
| ~~**Lambda never deployed**~~ — **resolved 2026-08-01** | The "deployed on AWS" requirement was not satisfiable by inspection | Deployed to `continuum` / eu-central-1. Two packaging bugs surfaced and were fixed on the way: `CodeUri: ../` pulled the root `requirements.txt` into the function (387 MB vs a 250 MB limit — now `infra/requirements-lambda.txt`), and a stray `template` key in `samconfig.toml` would have deployed the *unbuilt* template |
| ~~**Live Bedrock path never executed**~~ — **resolved 2026-08-01** | Titan/Claude response handling was unproven; every run to date had used silent fallbacks | Both paths verified end to end: `embed()` returns 1024 floats matching `VECTOR(1024)`, `_propose_via_bedrock()` parsed real Claude output 3/3. Every step now records `reasoning_source` / `correlation_source` so the mode is visible rather than inferred |
| **No demo video** | A required submission material | Scripted in `DEMO_SCRIPT.md`, unrecorded |
| **No captured evidence runs** | `assets/chaos-run/` is scaffolding — capture plan and shot list only | No longer gated: the function is deployed, so the capture can show the real cold-Lambda recovery |
| **HF Space can't self-trigger an incident** | A first-time judge sees state but can't create any | Read-only by design (single write path); an incident-start CTA is not currently in scope |
| **Space panels are blank on first paint** | A first-time visitor sees an empty console until they click Refresh | Deliberate: `CONTINUUM_UI_LOAD_ON_OPEN` defaults to `0` and auto-refresh is off after a Request-Unit burn audit found the timer costing ~50 RU per refresh. Educational empty-state copy is in place; the trade is cluster cost against first-paint polish |
| **Transaction boundaries not surfaced in the UI** | The `SERIALIZABLE` checkpoint pair is load-bearing (ADR 009) but only visible in logs and the database | Real and structlog-logged on every step; not rendered as a distinct console element |
| ~~**Matched precedent not shown in the console**~~ — **resolved 2026-08-02** | The vector search's *result* — which past incident was matched — was invisible in the UI | Each step now persists the precedent it was reasoned from into `remediation_steps.detail` (incident id, L2 distance, summary, rank, candidates considered) and the timeline renders it. It shows the match the proposal **cited**, not merely the nearest one — a unit test pins that distinction |
| **No judge-experience dry run** | The "understands it in 60 seconds" claim is untested against a fresh viewer | Subjective and unverifiable from repo state; needs one real walkthrough with someone who has not seen the project |

## Feedback for Cockroach Labs *(optional submission item — draft)*

- **Managed MCP Server:** the service-account key authenticates successfully but every query returns
  `unauthorized` until the account is granted the **Cluster Operator** role. The failure mode looks
  like a bad key rather than a missing role, which cost real debugging time. Surfacing "authenticated
  but unauthorized for this cluster" distinctly would have made it a one-minute fix.
- **MCP errors arrive wrapped in an anyio `TaskGroup`**, so a client that doesn't unwrap
  `ExceptionGroup`s recursively shows users `unhandled errors in a TaskGroup (1 sub-exception)`
  instead of the real message. Worth flattening at the SDK boundary.
- **Vector indexing** was the smoothest part of the build — `VECTOR(1024)` plus a `service`-prefixed
  C-SPANN index meant correlation stayed ordinary SQL, with structured filters and `<->` ranking in
  one round trip and no second datastore to keep consistent. That single-store property is the
  reason the recovery guarantee is simple enough to prove.
