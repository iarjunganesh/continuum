.PHONY: install migrate seed-data seed-data-offline run-api run-ui demo chaos-demo benchmark probe-bedrock deploy test lint coverage

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

# Latency benchmarks against $COCKROACH_DATABASE_URL — writes docs/BENCHMARKS.md.
benchmark:
	python scripts/benchmark.py --out docs/BENCHMARKS.md

# One InvokeModel + one Converse per candidate region, retries disabled — run
# before the demo; quotas are dynamic and usually closed (ADR 008 addendum).
probe-bedrock:
	python scripts/probe_bedrock.py

# Orchestrator -> Lambda (docs/DEPLOY.md). --use-container is required on
# Windows/macOS hosts: psycopg[binary]/pydantic-core need Linux wheels.
# First deploy is interactive: run the `sam deploy --guided` line from
# docs/DEPLOY.md once to create samconfig.toml, then use this target.
deploy:
	sam build --use-container --template infra/template.yaml
	sam deploy

test:
	pytest tests/unit tests/integration -v

coverage:
	pytest tests/unit tests/integration --cov=agents --cov=api --cov=observability --cov-report=term-missing

lint:
	ruff check .
