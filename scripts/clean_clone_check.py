"""
Prove the repository actually runs from a clean clone, following only the README.

`submission/SUBMISSION.md` carries the line *"Repo runs from a clean clone
following only the README instructions"*, and it stayed unticked for a long time
for a good reason: it cannot be checked on the machine that already has
everything installed. Every import resolves, every credential is already in the
environment, and a missing dependency is invisible because it was installed
months ago for something else.

This script removes the part of that problem which is actually removable. It
clones the **public** repository into a throwaway directory, builds a **fresh
virtualenv**, installs from `requirements.txt` alone, and then runs the README's
own Quick Start steps inside that clone — imports, the unit suite, schema apply,
a seed, and a live API answering `/api/v1/health` and the MCP-backed
`/api/v1/incidents/open`.

What it proves: the committed dependency set is sufficient, no module depends on
a file that was never committed, and the documented commands work in the order
the README gives them.

What it does **not** prove, stated here rather than left for a reader to find:

* The host still supplies Python itself, a C toolchain for any wheel that needs
  one, and a working network. A judge on a machine with no Python 3.14 hits a
  wall this script cannot see.
* Credentials come from an existing `.env`, copied in. A judge starts from
  `.env.example` and fills it in by hand; that step is human and is not tested.
* It clones a **branch**, so it verifies what is pushed — not what is in the
  working tree. That is deliberate: the pushed state is what a judge gets.

The seed step is deliberately run **without** `--replace-embeddings`, so it is
`ON CONFLICT DO NOTHING` and cannot overwrite the demo cluster's real Titan
vectors with anything. See `CLAUDE.md` on why that flag is load-bearing.

Usage:
    python scripts/clean_clone_check.py
    python scripts/clean_clone_check.py --workdir D:/tmp/cc --keep
    python scripts/clean_clone_check.py --ref v0.9.5 --skip-db
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.evidence import new_run  # noqa: E402

DEFAULT_REMOTE = "https://github.com/iarjunganesh/continuum.git"


class Step:
    """One README instruction, with its real outcome recorded either way."""

    def __init__(self, name: str, why: str):
        self.name = name
        self.why = why
        self.ok: bool | None = None
        self.seconds = 0.0
        self.detail = ""

    def as_dict(self) -> dict:
        return {
            "step": self.name,
            "proves": self.why,
            "ok": self.ok,
            "seconds": round(self.seconds, 1),
            "detail": self.detail[-4000:],
        }


def _run(cmd: list[str], cwd: Path, step: Step, env: dict | None = None, timeout: int = 1800) -> bool:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )
        step.seconds = time.perf_counter() - start
        step.ok = proc.returncode == 0
        step.detail = (proc.stdout + proc.stderr).strip()
    except Exception as exc:  # noqa: BLE001 — a failed step is a result, not a crash
        step.seconds = time.perf_counter() - start
        step.ok = False
        step.detail = repr(exc)
    print(f"  [{'ok ' if step.ok else 'FAIL'}] {step.name} ({step.seconds:.1f}s)")
    return bool(step.ok)


def _venv_python(clone: Path) -> Path:
    # The clone gets its own interpreter; the point is to install nothing from
    # the host's site-packages. `python -m venv` places it differently per OS.
    return clone / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")


def check(workdir: Path, remote: str, ref: str, env_file: Path | None, skip_db: bool, keep: bool) -> int:
    run = new_run("clean-clone", screenshots=False)
    clone = workdir / "continuum"
    steps: list[Step] = []
    results: dict = {
        "remote": remote,
        "ref": ref,
        "workdir": str(workdir),
        "host_python": sys.version.split()[0],
        "db_steps_run": not skip_db,
    }

    if clone.exists():
        shutil.rmtree(clone, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== clean clone check {run.short_id} · {remote}@{ref} ===\n")

    def step(name: str, why: str) -> Step:
        s = Step(name, why)
        steps.append(s)
        return s

    # 1. README step 1 — clone. From the public remote, not a local path: a
    #    local clone would carry objects that were never pushed.
    if not _run(
        ["git", "clone", "--depth", "1", "--branch", ref, remote, str(clone)],
        workdir,
        step("git clone", "the pushed branch is complete and checks out"),
    ):
        return _finish(run, results, steps, keep, workdir, clone)

    # Which commit a judge would actually get. The run manifest records *this*
    # working tree's HEAD, which is a different thing entirely — and the two
    # differing is exactly the case worth being able to see.
    results["cloned_commit"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=clone, capture_output=True, text=True
    ).stdout.strip()
    print(f"  cloned commit: {results['cloned_commit'][:12]}")

    # 2. README step 3 — a fresh interpreter, then install from requirements.txt
    #    alone. This is the step that catches a dependency that only works here
    #    because it was installed for something else.
    py = _venv_python(clone)
    if not _run(
        [sys.executable, "-m", "venv", ".venv"],
        clone,
        step("python -m venv .venv", "a fresh interpreter with no inherited packages"),
    ):
        return _finish(run, results, steps, keep, workdir, clone)
    if not _run(
        [str(py), "-m", "pip", "install", "-q", "-r", "requirements.txt"],
        clone,
        step("pip install -r requirements.txt", "the committed dependency set installs and is sufficient"),
    ):
        return _finish(run, results, steps, keep, workdir, clone)

    # 3. README step 2 — configure. A judge fills in .env.example by hand; here
    #    an existing .env is copied, and that difference is recorded rather than
    #    glossed over. Without it nothing that touches the cluster can run.
    s = step("cp .env", "the app reads its configuration from .env, not from the repo")
    if env_file and env_file.exists():
        shutil.copyfile(env_file, clone / ".env")
        s.ok, s.detail = True, f"copied {env_file.name} (contents never logged)"
    else:
        shutil.copyfile(clone / ".env.example", clone / ".env")
        s.ok, s.detail = True, "used .env.example — placeholder values, DB steps will be skipped"
        skip_db = True
        results["db_steps_run"] = False
    print(f"  [ok ] {s.name}")

    # 4. The import surface. Every entrypoint the README names, imported inside
    #    the clone's own interpreter — this is what catches a module that only
    #    resolves because of an uncommitted file.
    _run(
        [str(py), "-c", "import config, agents.orchestrator, agents.query_agent, api.main; print('imports ok')"],
        clone,
        step("import every entrypoint", "no module depends on a file that was never committed"),
    )

    # 5. The unit suite, inside the clone. Mocked at the import boundary, so it
    #    needs no cluster and no AWS — the one gate that is meaningful even when
    #    --skip-db is in force.
    _run(
        [str(py), "-m", "pytest", "tests/unit", "-q"],
        clone,
        step("pytest tests/unit", "the committed test suite passes against the committed code"),
    )

    if not skip_db:
        # 6. README step 4 — schema, then seed. Idempotent by construction:
        #    schema.sql is CREATE ... IF NOT EXISTS, and the seed omits
        #    --replace-embeddings so it can never overwrite real Titan vectors.
        _run(
            [
                str(py),
                "-c",
                "import psycopg, os; c = psycopg.connect(os.environ['COCKROACH_DATABASE_URL']); "
                "c.cursor().execute(open('infra/schema.sql').read()); c.commit(); print('schema applied')",
            ],
            clone,
            step("apply infra/schema.sql", "the documented schema applies to a live cluster"),
            env=_env_from(clone),
        )
        _run(
            [
                str(py),
                "scripts/seed_memory.py",
                "--file",
                "data/synthetic/incidents_seed.jsonl",
                "--from-fixture",
                "data/synthetic/seed_embeddings.json",
            ],
            clone,
            step("seed from the committed fixture", "seeding needs no AWS call and no live Bedrock"),
            env=_env_from(clone),
        )

        # 7. README step 5 — the API actually serves. Booted from the clone, hit
        #    over HTTP: /health is local, /incidents/open goes through the
        #    Managed MCP Server, so this covers the live MCP round trip too.
        _serve_and_probe(py, clone, step, steps)

    results["steps_passed"] = sum(1 for s in steps if s.ok)
    results["steps_total"] = len(steps)
    results["outcome"] = "PASS" if all(s.ok for s in steps) else "FAIL"
    return _finish(run, results, steps, keep, workdir, clone)


def _env_from(clone: Path) -> dict:
    """Load the clone's .env into a subprocess environment.

    Values are passed through to the child and never printed; the report records
    which keys were present, never what they were.
    """
    env: dict[str, str] = {}
    path = clone / ".env"
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _serve_and_probe(py: Path, clone: Path, step, steps: list[Step]) -> None:
    import urllib.request

    s = step("uvicorn + GET /api/v1/health", "the documented run command serves the documented endpoint")
    s2 = step("GET /api/v1/incidents/open", "the live MCP round trip works from a clean install")
    proc = subprocess.Popen(
        [str(py), "-m", "uvicorn", "api.main:app", "--port", "8123"],
        cwd=clone,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, **_env_from(clone)},
    )
    try:
        start = time.perf_counter()
        deadline = start + 90
        while time.perf_counter() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8123/api/v1/health", timeout=2) as r:
                    s.ok = r.status == 200
                    s.detail = f"HTTP {r.status} {r.read()[:200].decode('utf-8', 'replace')}"
                    break
            except Exception:  # noqa: BLE001 — still booting
                if proc.poll() is not None:
                    s.ok, s.detail = False, "uvicorn exited before becoming healthy"
                    break
                time.sleep(0.5)
        s.seconds = time.perf_counter() - start
        if s.ok is None:
            s.ok, s.detail = False, "never became healthy within 90s"
        print(f"  [{'ok ' if s.ok else 'FAIL'}] {s.name} ({s.seconds:.1f}s)")

        start = time.perf_counter()
        try:
            with urllib.request.urlopen("http://127.0.0.1:8123/api/v1/incidents/open", timeout=60) as r:
                body = r.read().decode("utf-8", "replace")
                s2.ok = r.status == 200
                s2.detail = f"HTTP {r.status} · {len(body)} bytes"
        except Exception as exc:  # noqa: BLE001
            s2.ok, s2.detail = False, repr(exc)
        s2.seconds = time.perf_counter() - start
        print(f"  [{'ok ' if s2.ok else 'FAIL'}] {s2.name} ({s2.seconds:.1f}s)")
    finally:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass


def _finish(run, results: dict, steps: list[Step], keep: bool, workdir: Path, clone: Path) -> int:
    results.setdefault("outcome", "FAIL")
    results.setdefault("steps_passed", sum(1 for s in steps if s.ok))
    results.setdefault("steps_total", len(steps))
    results["steps"] = [s.as_dict() for s in steps]
    run.write_json("clean-clone-check.json", results)
    run.write_text("NOTES.md", _notes(run.short_id, results, steps))
    manifest = run.finalize(extra={k: v for k, v in results.items() if k != "steps"})
    print(f"\n{results['outcome']} — {results['steps_passed']}/{results['steps_total']} steps")
    print(f"evidence: {run.dir.relative_to(REPO_ROOT)}")
    print(f"manifest: {manifest.relative_to(REPO_ROOT)}")
    if not keep:
        shutil.rmtree(clone, ignore_errors=True)
    else:
        print(f"clone kept at: {clone}")
    return 0 if results["outcome"] == "PASS" else 1


def _notes(short_id: str, results: dict, steps: list[Step]) -> str:
    lines = [
        f"# Clean-clone check `{short_id}` — {results['outcome']}",
        "",
        f"- remote: `{results['remote']}` @ `{results['ref']}`",
        f"- host Python: `{results['host_python']}`",
        f"- cluster-touching steps run: **{results['db_steps_run']}**",
        f"- steps passed: **{results['steps_passed']}/{results['steps_total']}**",
        "",
        "| Step | Proves | Result | Seconds |",
        "| --- | --- | --- | --- |",
    ]
    for s in steps:
        lines.append(f"| `{s.name}` | {s.why} | {'PASS' if s.ok else 'FAIL'} | {s.seconds:.1f} |")
    lines += [
        "",
        "## What this does not prove",
        "",
        "- The host still supplied Python, a compiler for any wheel needing one, and a network.",
        "- Credentials were copied from an existing `.env`; filling in `.env.example` by hand is untested.",
        "- It clones a pushed branch, so it verifies what a judge would `git clone` — not the working tree.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workdir", default=None, help="throwaway directory for the clone (default: a temp dir)")
    p.add_argument("--remote", default=DEFAULT_REMOTE, help="clone from here — the PUBLIC remote by default")
    p.add_argument("--ref", default="main", help="branch or tag to clone")
    p.add_argument(
        "--env-file",
        default=str(REPO_ROOT / ".env"),
        help="an existing .env copied into the clone; without it the cluster steps are skipped",
    )
    p.add_argument("--skip-db", action="store_true", help="imports + unit suite only; never touches a cluster")
    p.add_argument("--keep", action="store_true", help="leave the clone on disk for inspection")
    args = p.parse_args()

    import tempfile

    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="continuum-cc-"))
    env_file = Path(args.env_file) if args.env_file else None
    sys.exit(check(workdir, args.remote, args.ref, env_file, args.skip_db, args.keep))


if __name__ == "__main__":
    main()
