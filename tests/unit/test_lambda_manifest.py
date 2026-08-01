"""The Lambda manifest is a subset of the root requirements — pin it as one.

`infra/requirements-lambda.txt` exists because `CodeUri: ../` would otherwise
make SAM install the repo-root `requirements.txt` into the function, shipping
the Gradio UI and the dev toolchain and blowing Lambda's 250 MB unzipped limit.

That leaves two pin lists that must agree. If they drift, the deployed function
runs versions CI never tested, and nothing would say so until something failed
in production. These tests are the guard.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ROOT_REQUIREMENTS = REPO_ROOT / "requirements.txt"
LAMBDA_MANIFEST = REPO_ROOT / "infra" / "requirements-lambda.txt"

# Package name up to the first version specifier or extras bracket.
_NAME = re.compile(r"^([A-Za-z0-9._-]+)")


def _parse(path: Path) -> dict[str, str]:
    """Map normalised package name -> full requirement line."""
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _NAME.match(line)
        assert match, f"unparseable requirement in {path.name}: {line!r}"
        out[match.group(1).lower().replace("_", "-")] = line
    return out


def test_every_lambda_dependency_is_pinned_identically_in_the_root_file():
    """A looser or newer pin in either file means the Lambda runs something the
    test suite never exercised."""
    root = _parse(ROOT_REQUIREMENTS)
    lambda_deps = _parse(LAMBDA_MANIFEST)

    assert lambda_deps, "the Lambda manifest parsed as empty — check the format"

    mismatched = {name: (spec, root.get(name)) for name, spec in lambda_deps.items() if root.get(name) != spec}
    assert not mismatched, (
        f"Lambda manifest has drifted from requirements.txt. Each entry is name: (lambda_pin, root_pin): {mismatched}"
    )


def test_manifest_excludes_the_packages_that_blew_the_size_limit():
    """Regression guard for the 387 MB artifact. These are UI/test/tooling
    dependencies with no path from infra/lambda_handler.py — if one reappears
    here, the deployment package grows for no reason."""
    lambda_deps = _parse(LAMBDA_MANIFEST)

    never_in_lambda = {"gradio", "pytest", "pytest-cov", "ruff", "mypy", "uvicorn", "psutil"}
    leaked = never_in_lambda & lambda_deps.keys()

    assert not leaked, f"UI/dev dependencies leaked into the Lambda manifest: {sorted(leaked)}"
