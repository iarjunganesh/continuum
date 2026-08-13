.PHONY: precision-check clean-clone-check chaos-capture-lambda chaos-capture-pause charts voiceover beat-clips obs-assets redact-evidence check-drift export-memory restore-memory deploy-restart-drill install migrate seed-data seed-data-offline run-api run-ui demo chaos-demo chaos-capture benchmark resilience-bench local-cluster local-cluster-down local-cluster-status probe-bedrock preflight-deploy deploy test lint format typecheck load-test devpost-readme coverage

install:
	pip install -r requirements.txt

# migrate + seed-data (Windows, no `make`: scripts/migrate_and_seed.ps1)
migrate:
	python -c "import psycopg, os; \
	conn = psycopg.connect(os.environ['COCKROACH_DATABASE_URL']); \
	cur = conn.cursor(); \
	cur.execute(open('infra/schema.sql').read()); \
	conn.commit(); \
	print('schema applied')"

seed-data:
	python scripts/generate_synthetic_incidents.py --out data/synthetic/incidents_seed.jsonl --count 40
	python scripts/seed_memory.py --file data/synthetic/incidents_seed.jsonl

# Populate the Space with NO Bedrock/AWS dependency (deterministic vectors) —
# useful while Bedrock is throttled (ADR 008). Real Titan vectors: capture once
# with scripts/capture_seed_embeddings.py, then seed_memory.py --from-fixture.
seed-data-offline:
	python scripts/generate_synthetic_incidents.py --out data/synthetic/incidents_seed.jsonl --count 40
	python scripts/seed_memory.py --file data/synthetic/incidents_seed.jsonl --no-embeddings

run-api:
	python -m uvicorn api.main:app --port 8000

run-ui:
	python ui/app.py

demo:
	python scripts/demo_run.py --tick --resume-check

# The kill-and-recover beat, end to end (POSIX; Windows: scripts/chaos_demo.ps1):
#  1. start the API, 2. fire an alert (a step takes STEP_EXECUTION_SECONDS to
#  "execute"), 3. hard-kill the API mid-execution, 4. restart, 5. fire the same
#  alert -> it resumes the interrupted step from CockroachDB, not from scratch.
chaos-demo:
	python -m uvicorn api.main:app --port 8000 & \
	sleep 3; \
	python scripts/demo_run.py --tick --via-api & \
	sleep 2; \
	python scripts/chaos_kill.py --port 8000; \
	sleep 1; \
	python -m uvicorn api.main:app --port 8000 & \
	sleep 3; \
	python scripts/demo_run.py --tick --via-api --resume-check; \
	python scripts/chaos_kill.py --port 8000

# The same kill as chaos-demo, but RECORDED: snapshots CockroachDB before the
# kill, while the step is frozen with no live process, and after the cold resume,
# into assets/chaos-run/local-<id>/. Fails loudly rather than emitting weak
# evidence if the kill misses the execution window or a step runs twice. Leaves
# the incident in the cluster on purpose so the console screenshots can show it.
chaos-capture:
	python scripts/chaos_capture.py

# The same capture, but it HOLDS at the frozen phase until you press ENTER. Use
# this for any run you intend to screenshot or film: the `executing` row with no
# live process exists only inside that pause. Once the run resolves the console
# shows `resolved`, and that state cannot be staged again after the fact.
chaos-capture-pause:
	python scripts/chaos_capture.py --pause

# The same three phases against the DEPLOYED function, with AWS delivering the
# kill: the function's timeout is lowered below its own step-execution window,
# so Lambda terminates the invocation mid-step with no catchable signal. The
# resume is a second cold invocation of the same function. Needs the admin
# profile (lambda:UpdateFunctionConfiguration) and AWS_ACCESS_KEY_ID /
# AWS_SECRET_ACCESS_KEY unset — static keys outrank a profile in boto3.
# Add --pause for the screenshot window. Restores the timeout unconditionally.
chaos-capture-lambda:
	python scripts/chaos_capture.py --via-lambda --profile $(AWS_PROFILE)

# Clone the PUBLIC repo into a throwaway dir, build a fresh venv, install from
# requirements.txt alone, and run the README's own Quick Start inside it. The
# submission checklist item "runs from a clean clone" cannot be checked on the
# machine that already has everything; this checks the part that can be.
# Records what it does NOT prove (host Python, hand-filled .env) in its report.
clean-clone-check:
	python scripts/clean_clone_check.py

# OBS-ready 1920x1080 sources from assets/provider-evidence/. Never downscales a
# still: short captures are padded, and anything taller than 1080 becomes a pan
# video instead, so evidence text stays legible. Needs ffmpeg.
obs-assets:
	python scripts/build_obs_assets.py

# Mask a person's photograph or an AWS account id in assets/provider-evidence/.
# Narrow and declared by design — the regions live in the script with a reason
# each, and it must never touch a metric, timestamp or identifier that any
# document cites. Idempotent; --check exits 1 if a declared region is unmasked.
redact-evidence:
	python scripts/redact_evidence.py

# Does the vector index retrieve precedent that shares the failure mode? Offline
# — committed fixture, pure-function baseline, no AWS and no cluster. Recomputes
# the precision@1 figure the README and both submission documents quote, which
# was measured once by hand and then never checked again.
precision-check:
	python scripts/precision_check.py

# Latency benchmarks against $COCKROACH_DATABASE_URL — writes docs/BENCHMARKS.md.
benchmark:
	python scripts/benchmark.py --out docs/BENCHMARKS.md

# One InvokeModel + one Converse per candidate region, retries disabled — run
# before the demo; quotas are dynamic and usually closed (ADR 008 addendum).
probe-bedrock:
	python scripts/probe_bedrock.py

# Correctness under adversity — kill storm, exactly-once under contention,
# concurrent-agent throughput, vector search at scale. Writes docs/RESILIENCE.md
# and an evidence folder under assets/. Sizes are small by default because this
# runs against a live cluster; raise with --kills / --agents / --max-vectors.
resilience-bench:
	python scripts/resilience_bench.py

# A local single-node CockroachDB — the same container CI uses, schema applied
# and vector indexing on. Benchmarks and chaos runs belong here, not on the
# Cloud cluster the demo Space and the deployed Lambda share: an N=200 bench run
# left 665 incidents there, 431 frozen mid-run, on the surface judges open.
# (Request Units were never the constraint — see docs/CLUSTER_OPS.md.)
# Correctness counts hold anywhere; published *latency* still belongs to the
# real cluster (see the module docstring).
local-cluster:
	python scripts/local_cluster.py up

local-cluster-down:
	python scripts/local_cluster.py down

local-cluster-status:
	python scripts/local_cluster.py status

# The last Never-Miss failure mode: replace the deployed CODE under an open
# incident and prove the resume still lands exactly once on the new build.
# Needs CLONE_DIR=<clean checkout> (CodeUri: ../ packages the repo root, so the
# working tree's .venv would blow Lambda's limit) and an admin-ish profile.
# Asserts CodeSha256 actually changed — a no-op deploy would pass while proving
# nothing. See docs/DEPLOY.md and `make preflight-deploy`.
deploy-restart-drill:
	python scripts/deploy_restart_drill.py --clone-dir $(CLONE_DIR) --profile $(or $(AWS_PROFILE),continuum-admin)

# Snapshot / restore the memory layer as JSONL (data/snapshots/). Insurance
# against the CockroachDB Basic org being deleted when trial credits lapse —
# the dataset is small, so a plain export removes that as an existential risk.
# restore-memory needs SNAPSHOT=<path>; both skip benchmark fixtures by design.
export-memory:
	python scripts/export_memory.py

restore-memory:
	python scripts/restore_memory.py --file $(SNAPSHOT)

# Render the newest evidence run to theme-aware SVG charts (assets/charts/).
# Generated, never screenshotted — a screenshot of a number is stale the moment
# the number changes, and every chart carries the run id that produced it.
charts:
	python scripts/build_charts.py

# Synthesise the demo narration with Amazon Polly and rebuild the caption track.
# scripts/generate_demo_voiceover.py owns the narration TEXT — edit it there, re-run,
# and paste the emitted table into submission/DEMO_SCRIPT.md. Needs polly:SynthesizeSpeech
# (AWS_PROFILE=continuum-admin; the default bedrock-only identity gets AccessDenied).
voiceover:
	python scripts/generate_demo_voiceover.py

# Render the demo video's moving beats from the committed stills (assets/demo-video/beats/).
# Two of those stills are over 12,000px tall and cannot be placed in a 16:9 timeline at all;
# this decides which window is on screen when, as reviewable keyframes rather than as an
# editor's drag handles. Needs ffmpeg on PATH.
beat-clips:
	python scripts/build_beat_clips.py

# Fails when a doc disagrees with the repo: version fields, future-dated
# claims, stated test/ADR counts, broken links, stale generated files.
# CI-gated — run before any commit that touched docs.
check-drift:
	python scripts/check_drift.py

preflight-deploy:
	python scripts/preflight_deploy.py

# Gated on the preflight so a missing Docker daemon or an under-privileged
# profile fails in seconds rather than minutes into a container build.
# CockroachDatabaseUrl is passed here, NOT stored in samconfig.toml — it is a
# live cluster credential (NoEcho in the template).
deploy: preflight-deploy
	sam build
	sam deploy --parameter-overrides CockroachDatabaseUrl="$$COCKROACH_DATABASE_URL"

test:
	pytest tests/unit tests/integration -v

coverage:
	pytest tests/unit tests/integration --cov=agents --cov=api --cov=observability --cov-report=term-missing

# Both halves are CI-gated (.github/workflows/ci.yml). `make format` rewrites;
# this only checks, so it fails the same way CI does.
lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

# Regenerate the Devpost paste mirror from README.md. CI runs the --check form,
# so a README edit without regenerating this fails the build rather than
# silently shipping a stale submission doc.
devpost-readme:
	python scripts/build_devpost_readme.py

# Same invocation CI gates on (.github/workflows/ci.yml).
typecheck:
	mypy agents/ api/ observability/ config.py

# Read-path smoke load. Requires k6 (https://k6.io) and a running API.
# Deliberately does NOT exercise POST /alert — see the note in the script.
load-test:
	k6 run tests/load/k6_smoke.js
