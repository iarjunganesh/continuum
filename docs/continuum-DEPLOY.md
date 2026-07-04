# Deploying the Demo to Hugging Face Spaces

Continuum's public demo (`ui/app.py`) needs almost nothing running behind it — it's a read-only Gradio view straight into CockroachDB. No AWS credentials are needed on the Space itself; only the orchestrator (running separately, via `make run-api` locally or on Lambda) needs AWS access. This keeps the public Space's secret surface to exactly one value.

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

4. **Add the database secret on the Space itself** (not GitHub — this is separate)
   - Space page → Settings → Repository secrets → New secret
   - Name: `COCKROACH_DATABASE_URL` · Value: your CockroachDB connection string
   - This is the only secret the public Space needs — `ui/app.py` only reads incident/remediation state, it never calls Bedrock or writes anything

5. **Push to `main`**
   - The workflow force-pushes the full repo to the Space
   - The Space picks up the README frontmatter (`sdk: gradio`, `app_file: ui/app.py`) and builds automatically
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
