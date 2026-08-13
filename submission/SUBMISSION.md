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
      live, and the orchestrator runs on AWS Lambda in eu-central-1 (first deployed 2026-08-01, redeployed
      repeatedly on 2026-08-07; `docs/DEPLOY.md` carries the log). The
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
        `arn:aws:lambda:eu-central-1:<account-id>:function:continuum-orchestrator`, stack
        `continuum`. No provisioned concurrency (ADR 002) — cold start 1806 ms init, 130 MB of a
        512 MB allocation, sampled 2026-08-08 on the `v0.9.5` build (`v0.9.6` changed no
        application code). Since `v0.9.5` the function is
        deployed by CI on a version tag via GitHub OIDC (ADR 010), so the live function and the
        newest tag cannot drift apart

## Submission Materials

- [x] **Public GitHub repo** with MIT `LICENSE`
  - [x] License visible in the repo's **About** sidebar — GitHub detects it as `MIT` / *MIT
        License*, confirmed 2026-08-08 against the repository API's `license.spdx_id`, which is the
        same field that renders the sidebar. Checking that the file exists would not have proven
        this; an undetected licence file shows nothing in About
- [x] **README** with setup/run instructions, dependencies, and example config (`.env.example`)
- [x] **Functional demo app URL**
  - [x] Deployed to Hugging Face Spaces (`docs/DEPLOY.md`) — free, cardless, auto-synced on push
  - [x] Space secrets `COCKROACH_DATABASE_URL` + `COCKROACH_MCP_CLUSTER_ID` set; Space builds
  - [x] **Unblocked 2026-08-06:** the cluster's 30-day free trial expired on 2026-08-03 and was
        restored by adding a payment method — no data lost, same cluster id. Verified live:
        connect 360 ms, `EXPLAIN` still plans `• vector search` on the C-SPANN index, embeddings
        intact. See the first row of Known Gaps and [`../docs/CLUSTER_OPS.md`](../docs/CLUSTER_OPS.md)
  - [x] URL confirmed publicly accessible — `https://iarjunganesh-continuum.hf.space/` returns
        **HTTP 200** to an unauthenticated request carrying no cookies or session at all, which is
        a stricter test than an incognito window. Re-check on submission day; a Space can be made
        private by an account setting long after it was verified public
  - [x] **Populated with seeded synthetic incidents, on real Titan vectors (2026-08-07).** 56
        incidents, 168 remediation steps, 40 embeddings — all `amazon.titan-embed-text-v2:0`.
        Counts read off the cluster on 2026-08-09; they grow by design as evidence runs and Lambda
        ticks are driven against the demo cluster, so the frame in
        `assets/provider-evidence/01` (49 / 139, captured 2026-08-08) reads lower and is not
        stale — it is a dated photograph of a moving number.
        The cluster had been seeded with `--no-embeddings` deterministic vectors, which
        [`scripts/synthetic_vectors.py`](../scripts/synthetic_vectors.py) states are "deliberately
        NOT semantically meaningful": measured **precision@1 of 55%**, and that only because
        duplicate summaries hash to identical vectors. Captured real vectors once into the
        committed fixture [`data/synthetic/seed_embeddings.json`](../data/synthetic/seed_embeddings.json)
        and replaced them — **precision@1 98%** (39/40 nearest neighbours share the failure mode),
        symptom separation +0.1043 → +0.4585. `EXPLAIN` re-verified: still `• vector search` on the
        C-SPANN index, `prefix spans: [/'checkout-api']`
- [x] **Demo video** (<3 min, public on YouTube/Vimeo) — https://youtu.be/LwD8__sKqa0, uploaded 2026-08-12.
      Verified by `ffprobe` on the uploaded file: **2:55.7**, 1920×1080, 30 fps, H.264 + AAC
  - [x] Shows the project functioning on its intended platform — the resume in beats 6–8 is a cold
        invocation of the deployed Lambda, and the durable row it wrote records `runtime: lambda`
        from the function's own `AWS_LAMBDA_FUNCTION_NAME`
  - [x] Shows the CockroachDB memory layer at work — the kill-and-resume beat, one continuous take
        with no cut between the kill and the resume
  - [x] **Public, not unlisted** — verified 2026-08-13 by an unauthenticated fetch with no cookies.
        Resolving the title and channel only proves it is not *private*; Public and Unlisted both
        serve the page to a signed-out visitor. The watch page's own embedded player metadata
        distinguishes them, and reports `"isUnlisted":false` alongside `"isPrivate":false` — so this
        is settled from outside YouTube Studio rather than taken on trust
  - [x] No third-party trademarks / unlicensed music — no music at all; the only third-party marks
        on screen are the providers' own consoles, which is what the evidence beats are
  - [x] **README badge wrapped in the YouTube URL** and the mirror regenerated.
        `check_drift.py` cannot catch this — a badge is an image URL, not a claim it parses
  - [x] No credentials or account IDs in any frame. For **stills** this is mechanical:
        `scripts/redact_evidence.py` requires every judge-facing screenshot to be declared (an
        empty region tuple if it needs no mask) and `--check` fails on an undeclared file or an
        unmasked region. **The gate now covers video too** — added 2026-08-12 after
        `mcp-query-take.mp4` shipped with the signed-in user's photograph in every frame because the
        globs matched only PNGs. The exported cut was additionally swept by hand: the three frames
        carrying browser chrome (`s03` at 0:36, the Lambda console at 2:11, the MCP take at 2:32)
        were checked visually and all masks survived — a mask burned into a PNG travels with its
        pixels, so the editor's slight scaling moves mask and content together
- [x] **Text description of features and functionality** — [`DEVPOST.md`](DEVPOST.md) +
      [`DEVPOST_README.md`](DEVPOST_README.md) (paste-ready mirror with absolute URLs)
- [x] **Every field on the Devpost submission form answered** — [`DEVPOST.md` § Devpost Form
      Answers](DEVPOST.md#devpost-form-answers) carries paste-ready text for each one: project name,
      elevator pitch, the 25 Built-with tags, demo URL and testing instructions, repo and license
      URLs, the CockroachDB/AWS tool selections, the meaningful-integration explanation, start date,
      pre-existing-code disclosure, and AI-tool disclosure. **Video link is the one field still
      open** — see the demo-video block above
- [x] **Explicit list: which CockroachDB tools used + how** — README § CockroachDB Tools Used,
      expanded in `DEVPOST.md`
- [x] **Explicit list: which AWS services used + how** — README § AWS Services Used
- [x] *Optional:* **architecture diagram** — two, in fact: components and the recovery sequence,
      both brand-themed renders in `assets/architecture/`
- [ ] *Optional:* feedback on CockroachDB AI tools/features — **drafted** at the end of this file;
      unchecked until it is pasted into the Devpost form, because writing it here does not submit it

## Pre-Submission Sanity Checks

- [x] Repo runs from a clean clone following only the README instructions — verified 2026-08-09 by
      `make clean-clone-check`, which clones the **public** repo into a throwaway directory, builds a
      fresh venv, installs from `requirements.txt` alone, and runs the README's own Quick Start
      inside it: **10/10 steps**, ending with a live `GET /api/v1/incidents/open` through the Managed
      MCP Server. Report: [`../assets/clean-clone-run/`](../assets/clean-clone-run/). It states its
      own limits rather than implying more: the host still supplied Python 3.14, and the `.env` was
      copied rather than filled in from `.env.example` by hand, so that step remains untested
- [x] No secrets committed — `.env` gitignored, `.env.example` holds placeholders only, `.mcp.json`
      uses environment expansion
- [x] Demo app accessible without login — `https://iarjunganesh-continuum.hf.space/` returned
      **HTTP 200** to a request carrying no cookies, no session and no `Authorization` header on
      2026-08-09. Re-check on submission day: an account setting can make a Space private long after
      it was verified public
- [ ] Video watched start to finish — **duration is verified**, the viewing passes are not.
      `ffprobe` on the exported file reports **2:55.7**, 1920×1080, 30 fps, and the audio is
      normalised to −14 LUFS. What remains is the two passes `DEMO_SCRIPT.md` asks for: once
      with audio off (the story must survive on picture and captions alone) and once with video
      off (the narration must stand up alone). Ticking this on the measurement alone would be
      exactly the decorative checkbox this file warns about
- [x] All CI gates green: ruff lint, ruff format, mypy, Devpost mirror freshness, 88 unit +
      9 integration tests, 100% coverage against a 90% gate
- [x] No broken links repo-wide (markdown links and HTML `src`/`srcset`/`href`)
- [x] No placeholder artifacts shipping as finished — pending items are marked pending explicitly

---

## Known Gaps — stated plainly

Last reviewed **2026-08-09**, top to bottom — a date rather than a version, because a version pin
here went stale three releases running while the rows underneath it moved. **Resolved rows are
struck through and kept**, because a gap that quietly disappears reads worse than one that was
closed with evidence. Listing them is deliberate: a judge who finds
them unlisted reads the whole checklist as unreliable. This table is the **single** place open
gaps are tracked — `docs/DEMO_READINESS_CHECKLIST.md` previously duplicated it and was removed <!-- drift-allow-path: names a deleted file on purpose -->
once its findings were either closed with evidence or folded in here, because two gap lists
drift and the stale one is always the one a judge reads.

| Gap | Impact | Status |
| --- | --- | --- |
| ~~**The CockroachDB cluster is disabled — 30-day free trial expired, 2026-08-03**~~ — **resolved 2026-08-06** | For three days the cluster refused every connection with *"reached its Request Unit limit for the month"*, `max connections = 0`, taking the public demo down. The error names a Request Unit limit and was initially recorded here as overuse. It was not: the console read **3.42M of 400M RUs used** against $399 of $400 credits remaining. The trial was time-boxed to 30 days from cluster creation on 4 Jul and lapsed on schedule — a clock, not a meter | Resolved by adding a payment method to the existing org, which restored service on the **same cluster id shown in `assets/provider-evidence/`** and moved it to Basic's recurring $15/month allowance (50M RU + 10 GiB, against a measured 5.82M RU and 34.36 MiB on 2026-08-10 — so still $0). Resource limits are capped at 100M RU / 10 GiB, a $25 gross ceiling that nets to ≈$10 after the free credit. **No data was lost**; verified live on 2026-08-06 — 360 ms connect, 40 embeddings intact, `EXPLAIN` still planning `• vector search` on the C-SPANN index. Operating rules that keep it up are in [`../docs/CLUSTER_OPS.md`](../docs/CLUSTER_OPS.md); the misdiagnosis is written up in [`COSTS.md`](COSTS.md) |
| ~~**Lambda never deployed**~~ — **resolved 2026-08-01** | The "deployed on AWS" requirement was not satisfiable by inspection | Deployed to `continuum` / eu-central-1. Two packaging bugs surfaced and were fixed on the way: `CodeUri: ../` pulled the root `requirements.txt` into the function (387 MB vs a 250 MB limit — now `infra/requirements-lambda.txt`), and a stray `template` key in `samconfig.toml` would have deployed the *unbuilt* template |
| ~~**Live Bedrock path never executed**~~ — **resolved 2026-08-01** | Titan/Claude response handling was unproven; every run to date had used silent fallbacks | Both paths verified end to end: `embed()` returns 1024 floats matching `VECTOR(1024)`, `_propose_via_bedrock()` parsed real Claude output 3/3. Every step now records `reasoning_source` / `correlation_source` so the mode is visible rather than inferred |
| ~~**No demo video**~~ — **resolved 2026-08-12** | A required submission material | Shot, cut and uploaded: https://youtu.be/LwD8__sKqa0. 2:55.7 at 1920×1080/30, captions from `assets/demo-video/continuum.srt` uploaded with it. Beats 6–8 are one continuous take — a real `SIGKILL` against a live orchestrator, then a cold Lambda invocation resuming that exact `step_index`. Audio normalised to −14 LUFS (YouTube's own target) with the video stream copied bit-for-bit, verified by MD5 |
| ~~**No captured evidence runs**~~ — **fully resolved 2026-08-09** | `assets/chaos-run/` was scaffolding — capture plan and shot list only | `make chaos-capture` now performs the kill *and* records it. `assets/chaos-run/local-4789422d/` holds a real run: a live orchestrator hard-killed mid-step, the frozen `executing` row read back out of CockroachDB with no process alive to own it, and the cold resume of that exact step, with `correlation_source`/`reasoning_source` both `bedrock`. **Fully closed on 2026-08-09.** The Lambda half is `assets/chaos-run/lambda-c81826e7/` and `lambda-0b99a950/`, with AWS delivering the kill (see the row below). The **console screenshots are captured too** — two `--pause` runs, one per execution environment, shot live inside the window where the frozen row exists: `local-a2bb201d/screenshots/` (7 frames) and `lambda-0b99a950/screenshots/` (7 frames), each with a README mapping frame to claim. The frame that carries the argument — a step reading `executing` in Cockroach Labs' own UI with nothing alive to own it — exists in both |
| ~~**Lambda-side recovery has no `chaos-run` folder of its own**~~ — **resolved 2026-08-09** | The captured run was a local process kill | `make chaos-capture-lambda` now captures the same three phases against the deployed function, with **AWS delivering the kill**: the function's own timeout is lowered below its step-execution window, so Lambda terminates the invocation mid-step with no catchable signal, and the resume is a second cold invocation of the same function. Evidence: `assets/chaos-run/lambda-c81826e7/` and the screenshotted `lambda-0b99a950/` — step 0 frozen `executing` with no invocation alive to own it, resumed at that exact index, 3 steps executed, 0 duplicated, every durable step recording `runtime: lambda`, `correlation_source`/`reasoning_source` both `bedrock`. The folder carries the function's **own CloudWatch log** for the window: `INIT_START` on `python:3.14`, `step_checkpoint_start`, `REPORT … Status: timeout`, a *second* `INIT_START`, then `recovered_incident_state` with `last_step_status: executing`. The `CodeSha256` of the build under test is recorded, so the evidence names which function it came from. `lambda-0b99a950/screenshots/` carries the console frames for it, including CloudWatch showing the timeout and the second `INIT_START` **in a different log stream** |
| **Not a gap — kept because it explains the row above** | The Lambda capture stayed deprioritised for a week, and this is why | Recovery on the deployed function is evidenced **six** further independent ways: the deploy-restart drill (`assets/deploy-restart-run/dba642ed/`), the Lambda-timeout suite where **AWS** performs the kill, the cold-invocation latencies in `docs/BENCHMARKS.md`, a durable step written by the deployed function recording `runtime: lambda`, `reasoning_model_id` and `embedding_model_id` under its own IAM role, and — as of 2026-08-08 — the function's **own CloudWatch logs** in two forms: as text (`assets/provider-evidence/13.lambda-recovery-reads.txt`) and as a console frame (`assets/provider-evidence/11.lambda-log-stream-recovery.png`), both showing `recovered_incident_state` with `last_step_index` across cold invocations of one `correlation_id`, the frame with `INIT_START` on `python:3.14` immediately above it. That last one only became possible with `v0.9.5`; before it, `basicConfig()` was a no-op under the runtime's pre-installed root handler and every application log line the function emitted was discarded. The dedicated capture in the row above now exists as well, so the contract is proven on the deployed function directly *and* corroborated six ways around it |
| **Container / process-restart not proven separately** | One row of the failure-mode matrix has no dedicated harness | Deliberately subsumed: a Lambda timeout *is* the execution environment being taken away mid-step, under stricter conditions than a container restart — AWS delivers the kill, with no catchable signal. Stated rather than quietly folded away |
| **Bedrock quotas are dynamic and account-level** | Both Bedrock paths degrade *silently* by design, so a throttled account produces a demo that looks fine while never calling Bedrock | `make probe-bedrock` before any recording, and every step persists `reasoning_source` / `correlation_source` so the mode is visible in the durable row rather than inferred. Since 2026-08-07 a step that *did* reach Bedrock also records **which model** (`reasoning_model_id`, `embedding_model_id`, `bedrock_region`), and one that fell back records none — so the console can name the model rather than assert it. ADR 008 has the history |
| **HF Space can't self-trigger an incident** | A first-time judge sees state but can't create any | Read-only by design (single write path); an incident-start CTA is not currently in scope |
| **Space panels are blank on first paint** | A first-time visitor sees an empty console until they click Refresh | Deliberate: `CONTINUUM_UI_LOAD_ON_OPEN` defaults to `0` and auto-refresh is off after a Request-Unit burn audit found the timer costing ~50 RU per refresh. Educational empty-state copy is in place; the trade is cluster cost against first-paint polish |
| **Transaction boundaries not surfaced in the UI** | The `SERIALIZABLE` checkpoint pair is load-bearing (ADR 009) but only visible in logs and the database | Real and structlog-logged on every step; not rendered as a distinct console element |
| ~~**Matched precedent not shown in the console**~~ — **resolved 2026-08-02** | The vector search's *result* — which past incident was matched — was invisible in the UI | Each step now persists the precedent it was reasoned from into `remediation_steps.detail` (incident id, L2 distance, summary, rank, candidates considered) and the timeline renders it. It shows the match the proposal **cited**, not merely the nearest one — a unit test pins that distinction. Since 2026-08-07 it is also on the card itself, as `⌖ recalled #N of M` with the L2 distance |
| **Four pre-2026-08-07 steps show a recall rank with no distance** | On the live console two cards read `⌖ recalled #1 of 5` while newer ones read `⌖ recalled #1 of 5 · d=0.7902`. It looks like a missing value and is a deliberate refusal | Those steps predate `embedding_model_id`, so the vector space their distance was measured in cannot be attested — and this corpus *has* been re-embedded since, moving every distance from ~1.40 to ~0.64. Rendering the old number beside a Titan badge would assert the two were measured together. Rank still renders because "closest of five candidates" is true in any space. The console legend states the rule; `tests/unit/test_ui_kpis.py` pins it. Self-corrects as those incidents age out of the feed |
| **No judge-experience dry run** | The "understands it in 60 seconds" claim is untested against a fresh viewer | Subjective and unverifiable from repo state; needs one real walkthrough with someone who has not seen the project |

## Scope — things deliberately not built

Not oversights. Each was considered, costed, and declined for a stated reason, which is worth more
to a reader than a longer feature list would be.

- **Multi-region / regional failover.** Tempting for the "distributed database" story, but
  CockroachDB Basic needs **three** regions to survive a region failure, regions **cannot be removed
  once added**, and the trial credits are expiring. A one-way door with a recurring cost, days from
  a deadline. The recovery guarantee this project makes does not depend on it.
- **A third CockroachDB tool.** ADR 004: two tools that are load-bearing in the running app outscore
  three used decoratively, and the judging criteria contain no tool-count line.
- **An incident-start button in the Space.** Every write goes through one module (ADR 001); adding a
  UI write path to make the demo interactive would weaken the property the demo exists to prove.
- **Live observability (Grafana / CloudWatch dashboards).** structlog JSON and the CockroachDB
  console already show the state that matters. A dashboard would be a screenshot, not a capability.

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
