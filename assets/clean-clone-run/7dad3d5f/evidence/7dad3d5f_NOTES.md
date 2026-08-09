# Clean-clone check `7dad3d5f` — PASS

- remote: `https://github.com/iarjunganesh/continuum.git` @ `main`
- host Python: `3.14.6`
- cluster-touching steps run: **True**
- steps passed: **10/10**

| Step | Proves | Result | Seconds |
| --- | --- | --- | --- |
| `git clone` | the pushed branch is complete and checks out | PASS | 1.2 |
| `python -m venv .venv` | a fresh interpreter with no inherited packages | PASS | 2.4 |
| `pip install -r requirements.txt` | the committed dependency set installs and is sufficient | PASS | 25.6 |
| `cp .env` | the app reads its configuration from .env, not from the repo | PASS | 0.0 |
| `import every entrypoint` | no module depends on a file that was never committed | PASS | 1.0 |
| `pytest tests/unit` | the committed test suite passes against the committed code | PASS | 3.8 |
| `apply infra/schema.sql` | the documented schema applies to a live cluster | PASS | 0.5 |
| `seed from the committed fixture` | seeding needs no AWS call and no live Bedrock | PASS | 10.2 |
| `uvicorn + GET /api/v1/health` | the documented run command serves the documented endpoint | PASS | 1.0 |
| `GET /api/v1/incidents/open` | the live MCP round trip works from a clean install | PASS | 2.3 |

## What this does not prove

- The host still supplied Python, a compiler for any wheel needing one, and a network.
- Credentials were copied from an existing `.env`; filling in `.env.example` by hand is untested.
- It clones a pushed branch, so it verifies what a judge would `git clone` — not the working tree.
