# Prompts

Model-facing prompt templates, kept out of the Python source so they can be reviewed and
tuned without reading around control flow.

| File | Consumer |
| --- | --- |
| `remediation_agent.txt` | [`agents/remediation_agent.py`](../agents/remediation_agent.py) — Claude-on-Bedrock next-step reasoning |

The correlation agent has no prompt: it calls Titan for embeddings, not a chat model.

## Conventions

- `str.format()` placeholders, not f-strings — the file is data, not code.
- Literal braces in the desired JSON output are doubled (`{{`, `}}`) so `.format()` passes them
  through.
- **Loaded once at import time**, not lazily inside the Bedrock call. `agents/remediation_agent.py`
  wraps its Bedrock call in a broad `except Exception` that falls back to deterministic
  precedent-replay — a missing or unreadable prompt file caught *there* would be indistinguishable
  from a Bedrock outage and would degrade silently. Import-time loading makes it a loud, immediate
  failure instead.
- The prompt states the data is synthetic. Keep that line — it's part of the ADR 005 posture, not
  filler.

## Packaging note

`infra/template.yaml` sets `CodeUri: ../`, so this directory is included in the Lambda artifact.
If `CodeUri` is ever narrowed, this directory must be explicitly included or the function will
fail fast on cold start.
