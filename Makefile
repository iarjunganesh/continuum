.PHONY: install migrate seed-data run-api run-ui demo chaos-demo test lint coverage

install:
	pip install -r requirements.txt

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

test:
	pytest tests/unit tests/integration -v

coverage:
	pytest tests/unit tests/integration --cov=agents --cov=api --cov=observability --cov-report=term-missing

lint:
	ruff check .
