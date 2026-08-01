"""
Pre-deploy readiness check (`make preflight-deploy`).

`sam build` + `sam deploy` fail slowly and at different layers — a missing
Docker daemon surfaces minutes into a build, and an under-privileged IAM
identity only surfaces once CloudFormation is already being called. This
checks every precondition up front and reports all of them at once.

Checks, in the order they would otherwise bite:
  1. AWS SAM CLI on PATH
  2. Docker daemon reachable (`use_container = true` in samconfig.toml)
  3. AWS credentials resolve, and the identity can actually run CloudFormation
  4. COCKROACH_DATABASE_URL present (passed as a NoEcho template parameter)
  5. The packaged tree fits Lambda's unzipped size limit (CodeUri is the repo
     root, so a local .venv/ or .mypy_cache/ counts toward it)

Exit code is 0 only when every check passes, so it can gate `make deploy`.

Usage:
    python scripts/preflight_deploy.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STACK_REGION = "eu-central-1"
# AWS Lambda's hard limit on the unzipped deployment package.
LAMBDA_UNZIPPED_LIMIT_MB = 250

OK, FAIL = "OK", "FAIL"


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    # Resolve argv[0] to a full path first. On Windows the SAM CLI ships as a
    # `sam.CMD` shim, and subprocess uses CreateProcess, which does no PATHEXT
    # lookup — so a bare "sam" raises FileNotFoundError even though it is on
    # PATH and shutil.which() finds it. Without this, the check reports the
    # tool as missing on exactly the platform the deploy docs target.
    resolved = shutil.which(cmd[0])
    if resolved is None:
        return 127, "not found on PATH"
    try:
        proc = subprocess.run([resolved, *cmd[1:]], capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except OSError as exc:
        return 126, f"could not execute {resolved}: {exc}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"


def check_sam_cli() -> tuple[str, str]:
    if shutil.which("sam") is None:
        return (
            FAIL,
            "AWS SAM CLI not on PATH — https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html",
        )
    code, out = _run(["sam", "--version"])
    return (OK, out) if code == 0 else (FAIL, out)


def check_docker() -> tuple[str, str]:
    if shutil.which("docker") is None:
        return FAIL, "docker not on PATH — required because samconfig.toml sets use_container = true"
    code, out = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if code != 0:
        return FAIL, "Docker is installed but the daemon is not running — start Docker Desktop"
    return OK, f"daemon running (server {out})"


def check_aws_identity() -> tuple[str, str]:
    code, out = _run(["aws", "sts", "get-caller-identity", "--output", "text", "--query", "Arn"])
    if code != 0:
        return FAIL, f"no usable AWS credentials — {out.splitlines()[-1] if out else 'sts call failed'}"
    return OK, out


def check_deploy_permissions() -> tuple[str, str]:
    """The app's runtime identity is deliberately Bedrock-invoke only (see
    CLAUDE.md), so the default profile usually CANNOT deploy. Catch that here
    rather than partway through CloudFormation."""
    code, out = _run(
        ["aws", "cloudformation", "list-stacks", "--max-items", "1", "--region", STACK_REGION],
        timeout=45,
    )
    if code == 0:
        return OK, f"cloudformation:ListStacks allowed in {STACK_REGION}"
    if "AccessDenied" in out or "not authorized" in out:
        return FAIL, (
            "current identity cannot call CloudFormation — deploying needs an admin-ish profile "
            "(CloudFormation, IAM, Lambda, S3, ECR). Set AWS_PROFILE to it for the deploy; keep the "
            "Bedrock-only user as the function's runtime identity."
        )
    return FAIL, out.splitlines()[-1] if out else "cloudformation call failed"


def check_database_url() -> tuple[str, str]:
    url = os.getenv("COCKROACH_DATABASE_URL")
    if not url:
        return FAIL, "COCKROACH_DATABASE_URL is unset — it is passed as the NoEcho CockroachDatabaseUrl parameter"
    if "sslmode=" not in url:
        return FAIL, "COCKROACH_DATABASE_URL has no sslmode — use sslmode=require (ADR 005)"
    return OK, f"set, sslmode present ({len(url)} chars, value not shown)"


def check_package_size() -> tuple[str, str]:
    """template.yaml uses `CodeUri: ../`, so everything in the repo root is
    packaged. Measure it rather than checking for known offenders by name — the
    first version of this check looked only for `.venv` and would have sailed
    past a 152 MB `.mypy_cache` sitting right next to it."""
    biggest: list[tuple[float, str]] = []
    total = 0.0
    for child in REPO_ROOT.iterdir():
        if child.name == ".aws-sam":  # SAM's own build output, not packaged
            continue
        if child.is_file():
            size = child.stat().st_size / 1_048_576
        else:
            size = sum(f.stat().st_size for f in child.rglob("*") if f.is_file()) / 1_048_576
        total += size
        if size >= 1:
            biggest.append((size, child.name))

    if total <= LAMBDA_UNZIPPED_LIMIT_MB:
        return OK, f"packaged tree ~{total:.0f} MB, within Lambda's {LAMBDA_UNZIPPED_LIMIT_MB} MB unzipped limit"

    offenders = ", ".join(f"{name} {size:.0f} MB" for size, name in sorted(biggest, reverse=True)[:4])
    return FAIL, (
        f"packaged tree is ~{total:.0f} MB, over Lambda's {LAMBDA_UNZIPPED_LIMIT_MB} MB unzipped limit "
        f"(largest: {offenders}). Build from a clean checkout — `git clone` to a temp directory and "
        "deploy from there — rather than pruning your working tree"
    )


CHECKS = [
    ("AWS SAM CLI", check_sam_cli),
    ("Docker daemon", check_docker),
    ("AWS credentials", check_aws_identity),
    ("Deploy permissions", check_deploy_permissions),
    ("COCKROACH_DATABASE_URL", check_database_url),
    ("Packaging tree", check_package_size),
]


def main() -> int:
    print("Continuum — pre-deploy readiness check\n")
    failures = 0
    for name, check in CHECKS:
        try:
            status, detail = check()
        except Exception as exc:  # noqa: BLE001 — a preflight reports, it doesn't crash
            status, detail = FAIL, f"{type(exc).__name__}: {exc}"
        if status == FAIL:
            failures += 1
        print(f"  [{status:4}] {name}: {detail}")

    print()
    if failures:
        print(f"{failures} check(s) failed — `make deploy` would not succeed yet.")
        print("Bedrock access is NOT checked here; run `make probe-bedrock` separately.")
        return 1
    print("All checks passed. `make deploy` should succeed.")
    print("Bedrock quotas are dynamic — run `make probe-bedrock` before recording.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
