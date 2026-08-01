# Chaos Run Evidence

Captured kill-and-recover runs. One folder per run, named `<environment>-<short-id>`.

See [`../README.md`](../README.md) for the capture plan, the per-run folder layout, and the
numbered screenshot order.

## Capturing a run

1. `make probe-bedrock` — record which mode the run is in (live Bedrock vs. deterministic
   fallback). Save the output into the run's `evidence/`; do not omit it if it shows throttling.
2. `make benchmark` — cluster latencies for this run, into `evidence/<id>_benchmark.json`.
3. Drive the kill: `make chaos-demo` (POSIX) or `scripts\chaos_demo.ps1` (Windows), capturing
   the terminal transcript.
4. Snapshot the DB at each phase (before kill / frozen / after resume) into
   `evidence/<id>_remediation-steps.json`.
5. Screenshots into `screenshots/`, prefixed with the short id and numbered per the plan.

Every file is prefixed with the run's short id so files stay attributable if they're ever copied
out of their folder into a slide or a Devpost post.
