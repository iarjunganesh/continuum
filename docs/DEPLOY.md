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
   > `assets/demo-video/continuum.mp4` exists. <!-- drift-allow-path: names the final cut, which is deliberately not created yet -->

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

### The normal path: push a tag

**`.github/workflows/deploy.yml` deploys on any `v*.*.*` tag** ([ADR 010](adr/010-deploy-on-tag-from-ci.md)). Tagging is therefore an action that changes AWS, not just GitHub:

```bash
git push origin main --follow-tags
```

The job assumes an IAM role through GitHub's OIDC provider, builds, deploys, asserts `CodeSha256` actually moved, and invokes the deployed function once with an empty payload to prove the package imports. It writes a summary table naming the before and after hashes.

The invariant this buys: **the deployed function is the newest tag.** Before this existed the two drifted silently — the function ran a five-day-old build on 2026-08-07, and later sat two commits behind `v0.9.4`, both while looking entirely healthy.

It deliberately does **not** run on pushes to `main`. Redeploying during ordinary work would swap the code out from under a demo recording, which is the one moment the function must hold still.

The manual path below still works and is still the right tool for deploying an untagged commit, overriding `BedrockRegion` when a probe shows a region has closed, or debugging a build. `make deploy-restart-drill` also deploys directly, by design.

#### One-time setup for the CI deploy

Two repository secrets, and one IAM role the workflow cannot create for itself.

**1. Repository secrets** — GitHub repo → Settings → Secrets and variables → Actions:

| Secret | Value |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | the role ARN from step 2 |
| `COCKROACH_DATABASE_URL` | the same DSN used locally, with `sslmode=require` |

Prefer `gh secret set` over the web form for the DSN — it never puts the credential in a browser,
a clipboard history, or a screenshot:

```powershell
gh secret set COCKROACH_DATABASE_URL --body $env:COCKROACH_DATABASE_URL
gh secret set AWS_DEPLOY_ROLE_ARN --body $roleArn      # $roleArn from step 2
gh secret list
```

The DSN is a live cluster credential and this is a public repository. Repository secrets are encrypted and are never exposed to workflows from forked pull requests, and this workflow runs only on tags, which only a maintainer can push. It is a real disclosure surface, accepted knowingly, and the cluster holds only synthetic data (ADR 005).

**2. The OIDC provider and role.** Run once, as an admin identity:

```bash
# Trust GitHub's OIDC provider (skip if it already exists in the account)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com

# Trust policy — scoped to this repo AND to tag refs only, so a branch push
# cannot assume the role even if a workflow is added that tries.
cat > trust.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": { "token.actions.githubusercontent.com:sub": "repo:iarjunganesh/continuum:ref:refs/tags/*" }
    }
  }]
}
JSON

aws iam create-role --role-name continuum-deploy \
  --assume-role-policy-document file://trust.json

# Permissions. PowerUserAccess is NOT enough — the stack creates the
# function's execution role, so iam:* on that role is required.
aws iam attach-role-policy --role-name continuum-deploy \
  --policy-arn arn:aws:iam::aws:policy/AWSCloudFormationFullAccess
aws iam attach-role-policy --role-name continuum-deploy \
  --policy-arn arn:aws:iam::aws:policy/AWSLambda_FullAccess
aws iam attach-role-policy --role-name continuum-deploy \
  --policy-arn arn:aws:iam::aws:policy/IAMFullAccess
aws iam attach-role-policy --role-name continuum-deploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam get-role --role-name continuum-deploy --query Role.Arn --output text
```

**The same, in PowerShell 7+** — the account id is read from STS rather than pasted, so it never
lands in a file you might commit, and the trust policy is written to `$env:TEMP` rather than the
repo root for the same reason:

```powershell
$env:AWS_PROFILE = "continuum-admin"
Remove-Item Env:AWS_ACCESS_KEY_ID     -ErrorAction SilentlyContinue
Remove-Item Env:AWS_SECRET_ACCESS_KEY -ErrorAction SilentlyContinue
$acct = aws sts get-caller-identity --query Account --output text

# Already exists in the account? This errors EntityAlreadyExists — harmless, carry on.
aws iam create-open-id-connect-provider `
  --url https://token.actions.githubusercontent.com `
  --client-id-list sts.amazonaws.com

$trust = "$env:TEMP\continuum-trust.json"
@"
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::${acct}:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": { "token.actions.githubusercontent.com:sub": "repo:iarjunganesh/continuum:ref:refs/tags/*" }
    }
  }]
}
"@ | Set-Content -Encoding utf8 $trust

aws iam create-role --role-name continuum-deploy --assume-role-policy-document "file://$trust"

foreach ($p in @("AWSCloudFormationFullAccess","AWSLambda_FullAccess","IAMFullAccess","AmazonS3FullAccess")) {
  aws iam attach-role-policy --role-name continuum-deploy --policy-arn "arn:aws:iam::aws:policy/$p"
}

$roleArn = aws iam get-role --role-name continuum-deploy --query Role.Arn --output text
Remove-Item $trust
$roleArn
```

`${acct}` needs the braces — PowerShell parses a bare `$acct:` as a scope qualifier and the ARN
comes out malformed, which surfaces later as an opaque `InvalidParameterValue` on `create-role`
rather than as a syntax error.

The `sub` condition is the part that matters: without it, any workflow in any repository could assume the role. Scoping it to `refs/tags/*` in this repository means a branch push cannot deploy even if a future workflow tries.

`IAMFullAccess` is broader than ideal. SAM creates the function's execution role as part of the stack, so the deployer needs to create and pass IAM roles; narrowing it to the specific role paths this stack manages is worth doing if this outlives the hackathon.

### Prerequisites — check them first (manual path)

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

# --use-container is NOT optional on Windows (see the packaging note below):
# without it SAM bundles host-platform wheels for psycopg[binary] and
# pydantic-core, and the deploy succeeds while the function fails at import
# on Lambda's Linux runtime. Needs Docker Desktop running.
sam build --use-container
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

**Confirm the code actually moved.** `sam deploy` exits 0 on a no-op, and `fail_on_empty_changeset = false` in `samconfig.toml` makes that deliberate — so a successful-looking deploy proves nothing on its own:

```powershell
aws lambda get-function-configuration --function-name continuum-orchestrator `
  --region eu-central-1 --query "{CodeSha256:CodeSha256,LastModified:LastModified}" --output json
```

### Deployment log

Kept because a stale function is invisible from the repo, and the one thing that makes it dangerous is that everything still *works* — just as an older build.

| Date | `CodeSha256` | Cold start | Notes |
| --- | --- | --- | --- |
| 2026-08-01 | — | 1.71 s / 129 MB | First deploy; recovery contract observed across four cold invocations |
| 2026-08-02 | `0bpe5L/…` → `ylD4N19l…` | — | `make deploy-restart-drill` — code swapped under an open incident, resumed exactly once (`assets/deploy-restart-run/c1fe5151/`, superseded) |
| 2026-08-07 | `ylD4N19l…` → `cfj/1z90…` | **1719 ms / 130 MB** | Picked up the provenance fields (`_stack_detail`), the Titan reseed and the Alertmanager-shaped demo alert. The function had been **five days stale** |
| 2026-08-07 | `cfj/1z90…` → `r8pbqNx1…` | not re-measured | `make deploy-restart-drill` re-run on current code — code swapped under an open incident, resumed exactly once (`assets/deploy-restart-run/dba642ed/`) |
| 2026-08-07 18:33 UTC | `r8pbqNx1…` → `amvfjds9…` | not re-measured | Manual deploy of `v0.9.4` from the clean clone, so the live function matched the tag |
| 2026-08-07 18:44 UTC | `amvfjds9…` → *(recorded by the next deploy's summary)* | not re-measured | Manual deploy of `fb1c1e8` — the structlog `force=True` fix, without which the function wrote **no** application log lines at all |
| 2026-08-07 19:30 UTC | *(previous)* → `9SwDKNSy…` | **1806 ms / 130 MB** | **First CI deploy** — tag `v0.9.5`, [run 31211694477](https://github.com/iarjunganesh/continuum/actions/runs/31211694477). OIDC role assumed, artifact 61 MB of 250 MB, hash asserted moved, empty-payload smoke test returned the expected `KeyError` from `handle_alert`. Cold start re-sampled 2026-08-08 on this build |
| 2026-08-08 17:10 UTC | `9SwDKNSy…` → `nofa9OMe…` | not re-measured | CI deploy, tag `v0.9.6`, [run 31268760275](https://github.com/iarjunganesh/continuum/actions/runs/31268760275) |
| 2026-08-08 17:20 UTC | `nofa9OMe…` → `fnkZoLML…` | not re-measured | CI deploy, `v0.9.6` re-pushed after the tag was re-pointed, [run 31269179844](https://github.com/iarjunganesh/continuum/actions/runs/31269179844) |
| 2026-08-08 17:39 UTC | `fnkZoLML…` → `FM6pWpgA…` | not re-measured | CI deploy, `v0.9.6` final, [run 31269972300](https://github.com/iarjunganesh/continuum/actions/runs/31269972300). The build both chaos captures in `assets/chaos-run/lambda-*/` were taken against |
| 2026-08-10 15:31 UTC | `FM6pWpgA…` → `zSustj1W…` | not re-measured | CI deploy, tag `v0.9.7`, [run 31403924394](https://github.com/iarjunganesh/continuum/actions/runs/31403924394). Confirmed live against `get-function-configuration` immediately after the run. No application code changed in this tag — docs, the drift checker and the Devpost mirror generator only — so `CodeSha256` moved because `CodeUri: ../` packages the repo root, not because the function behaves differently. `Timeout` verified back at 60 s |
| 2026-08-11 23:52 UTC | `zSustj1W…` → `Fdyjdg8K…` | not re-measured | CI deploy, tag `v1.0.0`, [run 31548123128](https://github.com/iarjunganesh/continuum/actions/runs/31548123128). The video-release sweep; no application code changed |
| 2026-08-11 23:58 UTC | `Fdyjdg8K…` → `fN4/fBis…` | not re-measured | CI deploy, `v1.0.0` re-pushed after the tag was re-pointed onto the CI fix (`ffmpeg` for the video redaction gate), [run 31548502260](https://github.com/iarjunganesh/continuum/actions/runs/31548502260). Read back from `get-function-configuration` with `--query CodeSha256` after the run. Still no application code in the diff — a workflow file and `CHANGELOG.md` — so the hash moved only because `CodeUri: ../` packages the repo root |
| 2026-08-13 11:30 UTC | `fN4/fBis…` → `1Dsdy2sM…` | not re-measured | CI deploy, `v1.0.0` re-pointed a second time, [run 31695682879](https://github.com/iarjunganesh/continuum/actions/runs/31695682879). The tag moved onto a claims audit — a precision@1 checker, its tests, and four documentation corrections — so again **no application code changed**, and the hash moved only because `CodeUri: ../` packages the repo root. Validated after the deploy by six cold invocations driving two incidents to `resolved`, every durable step recording `runtime: lambda` with both Bedrock model ids |
| 2026-08-13 11:52 UTC | `1Dsdy2sM…` → `K1MJQelo…` | not re-measured | CI deploy, `v1.0.0` re-pointed a third time onto the documentation sweep, [run 31697312375](https://github.com/iarjunganesh/continuum/actions/runs/31697312375). **This is the build currently live**, read back from `get-function-configuration` with `--query CodeSha256` after the run; `Timeout` verified at 60 s, `State: Active`. Markdown only in the diff — including the row above this one |

**From `v0.9.5` onward the hashes come from the CI deploy**, which prints them into the workflow
run summary ([ADR 010](adr/010-deploy-on-tag-from-ci.md)) — but **CI does not write this table; a
human copies them across, and that is where it breaks.** The three `v0.9.6` rows were reconstructed
from the run logs on **2026-08-10**, during a submission audit that found this log still naming
`9SwDKNSy…` as live while the function had been running `FM6pWpgA…` for two days. That is the
precise failure this log exists to prevent, in the file `CLAUDE.md` and the README both call *the
authority on what is currently live*. It was recoverable only because the run logs still held the
hashes; the `2026-08-07 18:44` row shows what happens when they don't — a hash nobody recorded at
the time cannot be recovered afterwards, only overwritten by the next deploy.

**Copying the summary into this table is the last step of tagging, not follow-up work.** The
`v0.9.5` and `v0.9.6` *after* hashes were both read back live from `aws lambda
get-function-configuration`; each *before* is the row above it.

**The final row cannot live inside the tag it describes, and chasing that is a loop.** The tag
*causes* the deploy, so the resulting `CodeSha256` does not exist until after the tag is pushed —
recording it means a commit on `main` that the tag does not contain, and re-pointing the tag to
include that commit triggers another deploy with another new hash. On 2026-08-13 that loop was
entered once before being written down here. The rule that ends it: **record the row on `main`
after the deploy and leave the tag where it is.** Nothing is lost, because `CodeUri: ../` means a
docs-only commit changes the artifact hash without changing a line of what the function runs — the
tag still names the code that is deployed, which is the whole of what ADR 010 guarantees.

**Cold start: 1806 ms init, 130 MB of 512 MB**, measured on `9SwDKNSy…` (tag `v0.9.5`) on
2026-08-08. It has **not** been re-sampled on the live `1Dsdy2sM…` build, and the figure is
published as a characteristic of the function rather than of one artifact: the long-published
**1719 ms** figure was measured on `cfj/1z90…`, and both sit inside the 1578–1806 ms spread every
sampled build has shown, with `Max Memory Used` holding at 129–130 MB throughout. Every tag since
— `v0.9.6`, `v0.9.7` and both `v1.0.0` deploys — changed no application code, only scripts, docs,
assets and tests, so there is no reason to expect it to move. Re-sample if that stops being true. Raw REPORT lines: [`../assets/provider-evidence/12.lambda-cold-starts.txt`](../assets/provider-evidence/12.lambda-cold-starts.txt).

**A filtered `Init Duration` query returns only cold starts, so it cannot tell you how often one
happens.** Back-to-back invocations *do* reuse a warm environment — three ticks driven on
2026-08-08 produced one `INIT_START`, not three. That costs this project nothing, because the
orchestrator re-reads CockroachDB first on every invocation whether the environment is warm or not
(ADR 002); the guarantee does not depend on the container being new. Don't narrate "every
invocation is a cold start" over this data — the honest claim is *no provisioned concurrency, and
state is re-read regardless*.

**Redeploy before recording.** Recording #1 resumes via `--via-lambda`, so a stale function puts a Lambda on camera that behaves differently from the repo — and nothing in the demo would reveal it.

Verify both runtimes are distinguishable after deploying, which is the one thing a unit test cannot show:

```powershell
python scripts/demo_run.py --tick --new              # writes detail.runtime = "local"
python scripts/demo_run.py --tick --via-lambda --new # writes detail.runtime = "lambda"
```

### Driving the demo through the deployed Lambda

After the smoke test passes, the alert-stream driver can target the deployed function instead of running the orchestrator in-process. This is what makes beat 8's narration — *"a cold Lambda invocation — a different machine, in a different region, with no memory of this"* — literally true rather than a figure of speech: the kill lands on a local process, and the row it leaves behind is picked up by the deployed function in eu-central-1:

```bash
python scripts/demo_run.py --tick --via-lambda   # invokes continuum-orchestrator in eu-central-1
```

It uses `LAMBDA_FUNCTION_NAME` / `AWS_REGION` from the environment (`config.Settings`), so no extra setup beyond the deploy itself.
