# ADR 010: Deploy the Orchestrator from CI, on Tag Only

## Status
Accepted

## Context
The Gradio Space has deployed itself on every push to `main` since `sync-to-hf-space.yml` existed. The Lambda — the component the project's differentiating claim actually runs on — was deployed by hand, and nothing anywhere reported whether the deployed function matched the repo.

That gap produced two failures on 2026-08-07, both of which looked like success at the time:

- The function had been **five days stale**, still running the 2026-08-02 build. It predated the KPI fix, `_stack_detail`, the Titan reseed and the current alert text. Recording #1 resumes via `--via-lambda`, so filming would have put a Lambda on camera behaving differently from the repo, with nothing in the demo revealing it.
- After tagging `v0.9.4`, the deployed build was **two commits behind the tag**. A judge invoking the function and a judge reading the tag would have seen different systems.

Neither was detectable without manually querying `CodeSha256` and knowing what to compare it to. The deploy is a single command; the problem was never difficulty, it was that nothing forced the command to run at the moment the repo claimed a version.

## Decision
**Deploy the orchestrator from GitHub Actions, triggered only by a `v*.*.*` tag** (`.github/workflows/deploy.yml`).

Three choices inside that, each load-bearing:

**Tags, not pushes to `main`.** A tag is a deliberate act; a push is not. Deploying every commit would redeploy the live function during ordinary work — including while the demo is being recorded against it, which is the one moment the function must not change underneath. Tags also make the invariant stateable in one sentence: *the deployed function is the newest tag.*

**GitHub OIDC, not stored AWS keys.** The workflow assumes an IAM role via GitHub's OIDC provider, scoped to this repository and to tag refs. Long-lived access keys in a public repository's secrets are a standing liability that no rotation policy really fixes; OIDC credentials are minted per run and expire with it.

**CI passes every stack parameter explicitly, including `CockroachDatabaseUrl`.** CloudFormation would let an update reuse the parameter value already stored on the stack, which would mean CI needed no database credential at all — attractive, and rejected. That value only exists because someone deployed by hand first, so every CI deploy would silently depend on an invisible bootstrap step, and the workflow could not stand the stack up from nothing. Reproducibility is the entire point of moving the deploy into CI; a deploy that works only against a stack a human already created is the same problem in a new place. The DSN is therefore a repository secret.

## Consequences
- **Two repository secrets are required**: `AWS_DEPLOY_ROLE_ARN` and `COCKROACH_DATABASE_URL`. A tag pushed before they exist fails the deploy job — loudly, which is the intent. The release itself still publishes, because `release.yml` is a separate workflow.
- **A live cluster credential now lives in GitHub.** Repository secrets are encrypted and are not exposed to workflows triggered by forked pull requests, and this workflow only runs on tags, which only a maintainer can push. It remains a real disclosure surface and is recorded here rather than assumed away. The credential is for a synthetic-data cluster (ADR 005); it is not a route to anything real. If that ever stops being true, move to an AWS-side secret store and have the function resolve it at runtime.
- **The IAM role is a manual, one-time setup** and cannot be created by the workflow it authorises. `docs/DEPLOY.md` carries the commands. This is the one piece of infrastructure that remains click-or-CLI work, which is an acceptable floor: the alternative is a bootstrap credential with more power than the thing it creates.
- **CI runs a bare `sam build`, with no arguments at all**, so `samconfig.toml` is the single source of build configuration — template, `manifest` and `use_container` alike. The first version passed `--template infra/template.yaml`, which made SAM resolve `samconfig.toml` relative to the template's directory rather than the working directory; finding none there, it silently applied *neither* the `infra/requirements-lambda.txt` manifest nor the container flag, resolved the root `requirements.txt` instead, and produced an artifact CloudFormation rejected for exceeding Lambda's 250 MB unzipped limit. The container build is a few seconds of overhead on a Linux runner where it is not strictly needed; a CI build that is byte-for-byte the local one is worth more than those seconds. **Do not "optimise" this by passing arguments back in.**
- **The workflow measures the built artifact before deploying.** An oversized package surfaces from CloudFormation as an opaque 400 several minutes in, after a rollback, with nothing naming the cause. A `du` against `.aws-sam/build` reports it in one line. `scripts/preflight_deploy.py` cannot cover this: it measures the *source* tree before dependencies are resolved, and the dependencies are the risk.
- **Tagging is now an outward-facing action.** `git push --follow-tags` mutates AWS. The release checklist in `CLAUDE.md` already required green gates before tagging; that requirement stops being a formality and becomes the thing standing between a bad commit and the live demo.
- **A rollback is a tag, not a console action.** Re-tagging an older commit and pushing redeploys it. Deleting a tag does not undo a deploy.
- **This does not cover the CockroachDB schema.** `make migrate` remains manual and deliberately so — an automated migration on tag would apply DDL to the cluster judges are reading, which is a different risk with a different answer.
- Full continuous deployment on every merge to `main` remains **rejected**, not deferred, for the recording reason above. If the project outlives the hackathon and the demo stops being filmed against the live function, that reasoning expires and this ADR should be revisited rather than quietly worked around.
