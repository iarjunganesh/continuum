# Demo Readiness Checklist

## Objective

Prepare Continuum for a winner-level demo where every interaction
reinforces one message:

> Continuum enables autonomous agents to survive failure because their
> memory is durable, transactional, and persisted in CockroachDB---not
> process memory.

## P0 --- Must Have

### Demo Story

-   [ ] First 30--60 seconds grab attention. *(no demo video recorded
    yet; README states this plainly and the YouTube badge is unlinked --- no
    placeholder URL ships)*
-   [ ] One clear narrative from start to finish. *(scripted in
    `submission/DEMO_SCRIPT.md`, not yet recorded/proven end to end)*
-   [x] No distracting features.

### Happy Path

-   [ ] Fresh deployment works. *(not exercised as part of this audit)*
-   [ ] Sample incident starts immediately. *(HF Space is read-only by
    design --- no UI control triggers an incident; only local
    `make demo` / `demo_run.py` can)*
-   [x] Agent checkpoints execution.
-   [x] Process is killed.
-   [x] Recovery resumes from CockroachDB.
-   [x] Incident completes successfully.

### Recovery Proof

-   [x] Correct execution step resumes.
-   [x] No duplicate actions.
-   [x] No skipped actions.
-   [ ] Repeatable recovery. *(exactly-once claim is designed to be
    idempotent, but no test/script runs more than one kill-recover
    cycle back to back to prove it)*

## P0 --- Hugging Face Space

-   [x] Landing page explains Continuum.
-   [ ] Clear call-to-action. *(only "Refresh now" / "Ask via MCP" ---
    nothing invites starting or triggering an incident)*
-   [ ] Sample incident available. *(Space is display-only)*
-   [ ] Empty state educates instead of only reporting status.
    *(educational copy exists, but `LOAD_ON_OPEN` now defaults to `0`
    as of the RU-burn fix, so panels are blank on first paint until
    the user clicks refresh)*
-   [ ] First-time visitors understand what to do. *(same manual-
    refresh-by-default gap, plus no incident-start CTA)*

## P0 --- CockroachDB Visibility

-   [x] Durable checkpoints visible.
-   [x] Recovery reads visible.
-   [ ] Transaction boundaries visible. *(explicit `SERIALIZABLE`
    transactions are real and logged, but not surfaced as a distinct
    UI element)*
-   [ ] Vector retrieval visible (if used). *(match count is logged;
    the matched precedent/vector result isn't shown in the console)*
-   [x] MCP interactions visible (if used).
-   [x] Benchmark numbers captured and presented (`docs/BENCHMARKS.md`).
    *(populated 2026-07-08 from a real `make benchmark` run against the
    live cluster: p50/p95/p99/mean for recovery read, vector search, both
    step commits, and the end-to-end resume path, with the
    measured-from-workstation caveat stated)*

## P1 --- Visual Clarity

-   [x] Logs readable.
-   [x] Terminology consistent.
-   [x] Layout polished.
-   [ ] Empty/loading/error states reviewed. *(error state is handled;
    no real loading indicator, and manual-refresh-by-default means
    first paint is a static blank rather than a loading state)*

## P1 --- Consistency

-   [x] README matches implementation.
-   [ ] Demo runbook matches implementation. *(now `submission/DEMO_SCRIPT.md`,
    which absorbed the former `docs/DEMO_RUNBOOK.md` so the graded flow has
    one source of truth; it documents the manual-refresh default in its
    "if a take goes wrong" table)*
-   [x] DEVPOST.md updated. *(now at `submission/DEVPOST.md`)*
-   [ ] Screenshots and diagrams current. *(`assets/` now carries the
    full capture plan and folder structure — `assets/README.md`,
    `assets/chaos-run/`, numbered shot list — but no captured runs yet.
    The README no longer claims screenshots that don't exist. Capture
    after the Lambda deploy so the evidence shows the deployed system.)*
-   [x] No documentation drift. *(full sweep at v0.7.0: Bedrock-clamp language
    updated everywhere after the 2026-08-06 lift, all moved-doc paths
    repointed, generated files gated in CI, 0 broken links repo-wide)*

## P1 --- Scenario Validation

-   [ ] Fresh deployment. *(not exercised as part of this audit)*
-   [ ] Empty database. *(code path exists, not exercised this pass)*
-   [x] Seeded data.
-   [x] Kill during execution.
-   [x] Cold restart.
-   [ ] Multiple recoveries. *(no back-to-back kill-recover cycle
    exercised)*
-   [x] Completed incident.

## Judge Experience

A first-time judge should answer YES within one minute. These are
subjective/human-facing and can't be verified from repo state alone
--- left unchecked pending an actual dry run with a fresh viewer:

-   [ ] I understand what Continuum does.
-   [ ] I understand why durable memory matters.
-   [ ] I saw a real recovery.
-   [ ] I understand why CockroachDB is essential.
-   [ ] I would remember this project tomorrow.

## Demo Freeze

After the demo flow is complete: - No new features. - Bug fixes only. -
Documentation updates. - UX polish. - Demo rehearsal.

## Definition of Done

-   Story is compelling.
-   CockroachDB is indispensable.
-   Recovery always succeeds.
-   Documentation and UI are aligned.
-   The innovation is obvious without explanation.

---

*Last audited **2026-08-06** against actual repo state (code, tests, docs,
Makefile). Biggest open blockers, in order: **no recorded demo video**; the
**orchestrator has never been deployed to Lambda**, which gates the judge-facing
evidence capture in `assets/chaos-run/`; **the live Bedrock path has never
executed** (the ADR 008 clamp lifted 2026-08-06, but every run to date used
silent fallbacks, so that code is unproven); and the HF Space still can't
self-trigger a sample incident for a first-time visitor.*
