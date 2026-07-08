# Deploying the Demo to Hugging Face Spaces

Continuum's public demo (`ui/app.py`) needs almost nothing running behind it — it's a read-only Gradio console straight into CockroachDB: a live incident feed with KPI tiles, a per-incident **recovery-timeline replay** (the step frozen in `executing` is where the process died), and an "Ask via MCP" panel that queries the same state through the CockroachDB Cloud Managed MCP Server. No AWS credentials are needed on the Space itself; only the orchestrator (running separately, via `make run-api` locally or on Lambda) needs AWS access.

The Space runs **Gradio 6** (pinned via `sdk_version: 6.19.0` in the README frontmatter). Because `app_file` is `ui/app.py` — a subdirectory — the app bootstraps the repo root onto `sys.path` before importing `agents`/`config`, so it builds whether the host runs it as a script or launches `demo` directly.

## One-time setup

1. **Create the Space**
   - Go to [huggingface.co/new-space](https://huggingface.co/new-space)
   - Owner: your account · Space name: `continuum`
   - SDK: **Gradio** · Visibility: **Public**
   - Leave it empty — the GitHub Action pushes the code in

2. **Generate an HF access token**
   - [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → New token → **Write** scope
   - Copy it, you won't see it again

3. **Add the token as a GitHub repo secret**
   - GitHub repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `HF_TOKEN` · Value: the token from step 2
   - This lets `.github/workflows/sync-to-hf-space.yml` push to your Space on every merge to `main`

4. **Add secrets on the Space itself** (not GitHub — this is separate)
   - Space page → Settings → Repository secrets → New secret
   - `COCKROACH_DATABASE_URL` — required; the live incident table reads directly from CockroachDB. Use `?sslmode=require` (see `.env.example`) — CockroachDB Cloud's cert is signed by a cluster-specific CA, so `verify-full` needs that exact CA file on disk (not present in a fresh container) or it fails with `root certificate file does not exist` / `certificate verify failed`. `require` still encrypts the connection; it's an acceptable trade-off here since Continuum only ever stores synthetic data (ADR 005)
   - `COCKROACH_MCP_API_KEY` — optional; without it the "Ask via MCP" panel fails gracefully with a visible error instead of crashing the Space, so it's safe to omit if you haven't provisioned an MCP service-account key yet
   - `ui/app.py` never calls Bedrock or writes anything — no AWS credentials belong on the Space

5. **Push to `main`**
   - The workflow force-pushes the full repo to the Space
   - The Space picks up the README frontmatter (`sdk: gradio`, `sdk_version: 6.19.0`, `app_file: ui/app.py`) and builds automatically
   - Build takes ~1-2 minutes on CPU Basic; watch progress on the Space page

## Local test before deploying

```bash
export COCKROACH_DATABASE_URL="postgresql://..."
python ui/app.py
```

If this renders the incident table locally, the Space will render it too — the code path is identical, only the hosting differs.

## What's NOT on the Space

- The orchestrator (Lambda function) — runs separately, invoked by the alert stream, writes to CockroachDB
- `scripts/chaos_kill.py` — run locally/from your machine during the demo recording, not from the Space
- AWS credentials of any kind — the Space is display-only

This split is deliberate: the Space is the *window* into the memory, not the thing being tested for resilience. The resilience proof (kill-and-recover) happens in the orchestrator, which you run and record separately per `docs/DEMO_RUNBOOK.md`.

---

## Deploying the orchestrator to AWS Lambda

The orchestrator (`agents/orchestrator.py`, handler `infra.lambda_handler.lambda_handler`) is the thing that recovers state, and it deploys as a Lambda function from `infra/template.yaml` (AWS SAM). `python3.14` is a **managed Lambda runtime** (added November 2025, based on `provided.al2023`), so the template's `Runtime: python3.14` deploys as-is — no container image needed.

Prerequisites: AWS credentials with Lambda / IAM / CloudFormation access, the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html), and a reachable `COCKROACH_DATABASE_URL`.

```bash
# First deploy — interactive; saves your choices to samconfig.toml
sam build --use-container --template infra/template.yaml
sam deploy --guided --template infra/template.yaml \
  --stack-name continuum --region eu-central-1 \
  --parameter-overrides CockroachDatabaseUrl="$COCKROACH_DATABASE_URL" BedrockRegion=eu-north-1

# Subsequent deploys
make deploy   # = sam build --use-container + sam deploy (reuses samconfig.toml)
```

`--use-container` is **required when building on Windows or macOS**: without it, `sam build` bundles host-platform wheels for the compiled dependencies (`psycopg[binary]`, `pydantic-core`), and the resulting package crashes on Lambda's Linux runtime with import errors. The container build resolves Linux wheels regardless of host OS.

Region is **eu-central-1** (co-located with the CockroachDB cluster, ADR 007); Bedrock calls target **eu-north-1** by default (ADR 008 + addendum) — both already defaulted in the template's parameters. Bedrock quotas on this account are dynamic and usually closed; run `make probe-bedrock` first and override `BedrockRegion` if the probe shows a different region open. A throttled region does **not** break the deploy or the demo — correlation and reasoning degrade to their deterministic fallbacks by design.

**Packaging note.** The template's `CodeUri: ../` packages the repo root, so build from a checkout where the local `.venv/` is absent or moved aside — otherwise SAM bundles the virtualenv and blows past Lambda's unzipped-size limit. SAM installs the function's own dependencies from `requirements.txt`.

### Smoke test

```bash
sam remote invoke ContinuumOrchestratorFunction --stack-name continuum --region eu-central-1 \
  --event '{"correlation_id":"deploy-smoke-1","service":"checkout-api","region":"eu-central-1","severity":"high","text":"deploy smoke test"}'
```

Then confirm the write landed in CockroachDB:

```sql
SELECT state FROM incidents WHERE correlation_id = 'deploy-smoke-1';
```

Once that returns a row, check the **AWS Lambda** and **"Uses CockroachDB deployed on AWS"** items in `docs/SUBMISSION.md`.

### Driving the demo through the deployed Lambda

After the smoke test passes, the alert-stream driver can target the deployed function instead of running the orchestrator in-process — this is what makes "a fresh Lambda invocation starts cold" in `docs/DEMO_RUNBOOK.md` literally true:

```bash
python scripts/demo_run.py --tick --via-lambda   # invokes continuum-orchestrator in eu-central-1
```

It uses `LAMBDA_FUNCTION_NAME` / `AWS_REGION` from the environment (`config.Settings`), so no extra setup beyond the deploy itself.
