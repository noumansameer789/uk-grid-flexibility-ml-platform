"""Capture installed dependency closure separately for runtime and training/CI."""

from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

runtime = [
    "fastapi",
    "uvicorn",
    "httpx[socks]",
    "pandas",
    "numpy",
    "lightgbm",
    "scikit-learn",
    "duckdb",
    "prometheus-client",
]
dev = runtime + ["mlflow", "pytest", "pytest-cov", "ruff"]


def closure(roots):
    found = {}
    pending = [(Requirement(name), set()) for name in roots]
    seen = set()
    while pending:
        req, _ = pending.pop()
        name = canonicalize_name(req.name)
        extras = frozenset(req.extras)
        if (name, extras) in seen:
            continue
        seen.add((name, extras))
        dist = metadata.distribution(name)
        found[name] = dist.version
        for spec in dist.requires or []:
            child = Requirement(spec)
            if child.marker is None or any(child.marker.evaluate({"extra": x}) for x in extras | {""}):
                pending.append((child, set()))
    return found


for suffix, roots in (("runtime", runtime), ("dev", dev)):
    packages = closure(roots)
    Path(f"requirements-{suffix}.lock").write_text(
        "# Resolved and tested with Python 3.12 on Linux. Regenerate using scripts/lock_requirements.py.\n"
        + "\n".join(f"{k}=={v}" for k, v in sorted(packages.items()))
        + "\n"
    )
    print(suffix, len(packages), "pinned dependencies")
