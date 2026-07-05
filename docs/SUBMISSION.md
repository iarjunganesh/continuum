# Submission Checklist — CockroachDB × AWS Hackathon

Tracks directly against the [official rules](https://cockroachdb-ai.devpost.com/rules). Update as each item is completed.

## Eligibility / Build Constraints
- [ ] All code newly written during Submission Period (June 30 – Aug 18, 2026) — no reused code from ARGUS, Banker's Wrapped, or any pre-existing repo
- [ ] Any AI coding assistant / starter template usage disclosed in README
- [ ] All third-party data/APIs authorized for use (synthetic data only — see ADR 005)

## Required Project Requirements
- [ ] Uses CockroachDB as persistent memory layer, deployed on AWS — *code complete; AWS deployment (Lambda) still pending*
- [x] ≥2 CockroachDB tools meaningfully integrated (not just initialized):
  - [x] Distributed Vector Indexing — `incident_embeddings` + correlation queries
  - [x] CockroachDB Cloud Managed MCP Server — `agents/query_agent.py` calls it at runtime (not just a Claude Code dev convenience); see ADR 003
  - [x] ccloud CLI — evaluated and cut, not claimed as used (ADR 004 resolution)
- ≥1 AWS service:
  - [ ] AWS Lambda — SAM template (`infra/template.yaml`) ready; not yet deployed
  - [x] Amazon Bedrock — embeddings + reasoning, code complete and unit-tested

## Submission Materials
- [ ] Public GitHub repo with OSS license visible in About section (MIT — see `LICENSE`)
- [ ] README with clear setup/run instructions, dependencies, example config
- [ ] Functional demo app URL
  - [ ] Deployed to Hugging Face Spaces (`docs/DEPLOY.md`) — free, no card, permanent hosting
  - [ ] Space secret `COCKROACH_DATABASE_URL` set and Space builds successfully
  - [ ] URL confirmed publicly accessible in a private/incognito browser before submitting
- [ ] Demo video (<3 min, YouTube/Vimeo, public)
  - [ ] Shows the project functioning on its intended platform
  - [ ] Shows the CockroachDB memory layer at work (the kill-and-resume beat)
  - [ ] No third-party trademarks / unlicensed music
- [ ] Text description of features and functionality
- [ ] Explicit list: which CockroachDB tools used + how
- [ ] Explicit list: which AWS services used + how
- [ ] Optional: architecture diagram (have one — `docs/ARCHITECTURE.md` §1 + README)
- [ ] Optional: feedback on CockroachDB AI tools/features

## Pre-Submission Sanity Checks
- [ ] Repo runs from a clean clone following only the README instructions
- [ ] No secrets committed (`.env` gitignored, `.env.example` has placeholders only)
- [ ] Demo app accessible without login, or test credentials provided
- [ ] Video watched start-to-finish at <3:00 runtime
