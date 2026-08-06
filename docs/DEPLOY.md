# Deploying the Demo to Hugging Face Spaces

Continuum's public demo (`ui/app.py`) needs almost nothing running behind it — it's a read-only Gradio console straight into CockroachDB: a live incident feed with KPI tiles, a per-incident **recovery-timeline replay** (the step frozen in `executing` is where the process died), and an "Ask via MCP" panel that queries the same state through the CockroachDB Cloud Managed MCP Server. No AWS credentials are needed on the Space itself; only the orchestrator (running separately, via `make run-api` locally or on Lambda) needs AWS access.

The Space runs **Gradio 6** (pinned via `sdk_version` in the README frontmatter — currently `6.22.0`, and it must equal the `gradio` floor in `requirements.txt` or the Space build fails). Because `app_file` is `ui/app.py` — a subdirectory — the app bootstraps the repo root onto `sys.path` before importing `agents`/`config`, so it builds whether the host runs it as a script or launches `demo` directly.

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

   > **The Hub rejects binary files pushed over plain git** — PNG, MP4, MP3 and friends must go
   > through [Xet/LFS](https://huggingface.co/docs/hub/xet), and a plain push fails with
   > *"Your push was rejected because it contains binary files"* (`pre-receive hook declined`).
   > The sync workflow therefore strips binaries onto a throwaway commit before pushing. Nothing
   > the Space renders is binary — `README.md` embeds only SVGs — so the Space is unaffected, and
   > the binaries stay on GitHub where the judge-facing evidence lives. This will matter more once
   > `assets/demo-video/continuum.mp4` exists.

4. **Add secrets on the Space itself** (not GitHub — this is separate)
   - Space page → Settings → Repository secrets → New secret
   - `COCKROACH_DATABASE_URL` — required; the live incident table reads directly from CockroachDB. Use `?sslmode=require` (see `.env.example`) — it encrypts without needing a CA cert file, so it works in a fresh Space container unconditionally, and it's acceptable here because Continuum only stores synthetic data (ADR 005). **Do not** use `?sslmode=verify-full&sslrootcert=system` even though this cluster's cert is publicly-trusted: `sslrootcert=system` is unreliable through psycopg/libpq (empty/unresolved default CA store on many platforms) and fails with `certificate verify failed` — which is exactly the error you'll see if you leave `verify-full` in the string. After changing this secret, **restart the Space** — secrets are only re-read on restart.
   - `COCKROACH_MCP_API_KEY` **and** `COCKROACH_MCP_CLUSTER_ID` — optional as a pair; without them the "Ask via MCP" panel shows a visible setup message instead of crashing the Space. The key alone is not enough on two counts: the server scopes each session to a cluster via the cluster id (the UUID in the console URL), and the service account behind the key must hold the **Cluster Operator** (or Cluster Admin) role **on that cluster** — a key with no cluster role authenticates fine but every query fails with `unauthorized`. Console → Access Management → Service Accounts → your SA → Roles
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

This split is deliberate: the Space is the *window* into the memory, not the thing being tested for resilience. The resilience proof (kill-and-recover) happens in the orchestrator, which you run and record separately per `submission/DEMO_SCRIPT.md`.

---

## Deploying the orchestrator to AWS Lambda

The orchestrator (`agents/orchestrator.py`, handler `infra.lambda_handler.lambda_handler`) is the thing that recovers state, and it deploys as a Lambda function from `infra/template.yaml` (AWS SAM). `python3.14` is a **managed Lambda runtime** (added November 2025, based on `provided.al2023`), so the template's `Runtime: python3.14` deploys as-is — no container image needed.

### Prerequisites — check them first

```bash
make preflight-deploy                     # Windows: python scripts/preflight_deploy.py
```

`sam build` and `sam deploy` fail slowly and at different layers: a stopped Docker daemon surfaces minutes into a build, and an under-privileged IAM identity only surfaces once CloudFormation is already being called. `scripts/preflight_deploy.py` checks all of it up front and reports every failure at once, so one pass tells you everything to fix. `make deploy` is gated on it.

| Prerequisite | Notes |
| --- | --- |
| **AWS SAM CLI** | [Install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html). Not bundled with the AWS CLI — a separate install |
| **Docker, daemon running** | `samconfig.toml` sets `use_container = true`; the build needs a live daemon, not just the binary |
| **An admin-ish AWS profile** | **The app's own credentials cannot deploy.** `continuum-bedrock` is scoped to `bedrock:InvokeModel` on purpose, so it gets `AccessDenied` on CloudFormation. Deploy with a profile holding CloudFormation, IAM, Lambda, S3 and ECR — `export AWS_PROFILE=<admin>` for the deploy only, and leave the Bedrock-only user as the function's runtime identity |
| **`COCKROACH_DATABASE_URL`** | Passed as the `NoEcho` `CockroachDatabaseUrl` parameter. Must include `sslmode=require` (ADR 005) |
| **A packaged tree under 250 MB** | `CodeUri: ../` packages the **whole repo root**, so a local `.venv/` (~434 MB) or `.mypy_cache/` (~152 MB) counts toward Lambda's unzipped-size limit. The preflight measures the tree and names the offenders |

### Build from a clean checkout

A working tree carries build caches and a virtualenv that `CodeUri: ../` would package. Rather than pruning those out of the directory you work in — destructive, and easy to half-undo — clone the repo somewhere disposable and build there:

```bash
git clone --depth 1 https://github.com/iarjunganesh/continuum /tmp/continuum-build
cd /tmp/continuum-build
sam build
```

A clean checkout is ~6 MB. `sam build` needs **no AWS credentials**, so this step can be verified before any IAM setup exists.

### Deploying

```bash
make deploy   # preflight → sam build → sam deploy
```

`make deploy` builds in place and therefore assumes a clean tree; from a working directory with a virtualenv, use the clone above and run `sam deploy` there. Deploy with the admin profile only:

```bash
AWS_PROFILE=continuum-deploy sam deploy \
  --parameter-overrides CockroachDatabaseUrl="$COCKROACH_DATABASE_URL"
```

#### On Windows — PowerShell 7+

`make deploy` is one of the two POSIX-only targets (it relies on `$$VAR` expansion), so there is no
translation — run the three steps directly. **PowerShell has no inline `VAR=x command` prefix**, so
the profile must be set as an environment variable first:

```powershell
# 1. Clear the Bedrock-only static keys FIRST. This is the step that bites.
#    .env exports AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY for the runtime identity,
#    and boto3 and the AWS CLI both rank static keys ABOVE a named profile — so
#    $env:AWS_PROFILE is silently ignored and the failure arrives as an IAM
#    AccessDenied on CloudFormation rather than as a config error.
Remove-Item Env:AWS_ACCESS_KEY_ID     -ErrorAction SilentlyContinue
Remove-Item Env:AWS_SECRET_ACCESS_KEY -ErrorAction SilentlyContinue
Remove-Item Env:AWS_SESSION_TOKEN     -ErrorAction SilentlyContinue
$env:AWS_PROFILE = "continuum-admin"

# 2. Preflight — reports every failure at once
python scripts/preflight_deploy.py

# 3. Build from a clean clone; CodeUri: ../ packages the repo root,
#    so a local .venv would blow Lambda's 250 MB limit
git clone --depth 1 https://github.com/iarjunganesh/continuum "$env:TEMP\continuum-build"
Set-Location "$env:TEMP\continuum-build"
sam build
sam deploy --parameter-overrides CockroachDatabaseUrl="$env:COCKROACH_DATABASE_URL"
```

`python scripts/preflight_deploy.py` prints the identity it actually resolved — confirm it names the
admin profile and **not** `continuum-bedrock` before you let `sam deploy` run.

> **`AWS_PROFILE` alone will not switch identity here.** `.env` exports static
> `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` for the Bedrock-only user, and boto3 ranks
> static environment keys **above** the named profile — so the profile is silently ignored and
> the failure surfaces as an IAM `AccessDenied` on CloudFormation (or on `lambda:InvokeFunction`),
> which reads like a permissions problem on the admin user rather than a credential-precedence
> one. Clear them for the deploy shell first:
>
> ```bash
> unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY   # PowerShell: Remove-Item env:AWS_ACCESS_KEY_ID, env:AWS_SECRET_ACCESS_KEY
> export AWS_PROFILE=continuum-admin
> ```
>
> `make preflight-deploy` prints the identity it actually resolved — check it says the admin
> user, not `continuum-bedrock`.

`samconfig.toml` is **checked in**, so the deploy is reproducible rather than depending on whoever ran `sam deploy --guided` first. It carries the stack name, region, capabilities and container-build flag — but **deliberately not `CockroachDatabaseUrl`**, which is a live cluster credential and is passed from the environment by the `deploy` target instead.

To override the Bedrock region when a probe shows the default has closed:

```bash
sam deploy --parameter-overrides \
  CockroachDatabaseUrl="$COCKROACH_DATABASE_URL" BedrockRegion=eu-west-1
```

`--use-container` is **required when building on Windows or macOS**: without it, `sam build` bundles host-platform wheels for the compiled dependencies (`psycopg[binary]`, `pydantic-core`), and the resulting package crashes on Lambda's Linux runtime with import errors. The container build resolves Linux wheels regardless of host OS.

Everything now runs in **eu-central-1** — Lambda, CockroachDB (ADR 007) and Bedrock (ADR 008 addendum 3) — so the Bedrock leg is in-region rather than a cross-region hop. `BedrockRegion` remains a **separate template parameter** rather than reusing the stack region: Bedrock quotas on this account are dynamic and account-level, so being able to move Bedrock without redeploying the function is deliberate. Run `make probe-bedrock` first and override `BedrockRegion` if eu-central-1 has closed. A throttled region does **not** break the deploy or the demo — correlation and reasoning degrade to their deterministic fallbacks by design, and the `correlation_source` / `reasoning_source` fields on every step record which path actually ran.

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

Once that returns a row, check the **AWS Lambda** and **"Uses CockroachDB deployed on AWS"** items in `submission/SUBMISSION.md`.

### Driving the demo through the deployed Lambda

After the smoke test passes, the alert-stream driver can target the deployed function instead of running the orchestrator in-process — this is what makes "a fresh Lambda invocation starts cold" in `submission/DEMO_SCRIPT.md` literally true:

```bash
python scripts/demo_run.py --tick --via-lambda   # invokes continuum-orchestrator in eu-central-1
```

It uses `LAMBDA_FUNCTION_NAME` / `AWS_REGION` from the environment (`config.Settings`), so no extra setup beyond the deploy itself.
