"""Rerun everything: tests, the scored tables, the A/B pilot and every evaluation.

Usage:  DATA_DIR=... python scripts/run_all.py
Reports are written to WORK_DIR/reports/ (git-ignored, since they summarise restricted data).
Takes roughly 15 to 20 minutes on a laptop.
"""
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from wellsimple import config  # noqa: E402

STEPS = [
    ("tests", [sys.executable, "-m", "pytest", "-q"]),
    ("build_artifacts", [sys.executable, "scripts/build_artifacts.py"]),
    ("build_pilot", [sys.executable, "scripts/build_pilot.py"]),
    ("eval_risk", [sys.executable, "scripts/eval_risk.py"]),
    ("explain_risk", [sys.executable, "scripts/explain_risk.py"]),
    ("eval_physics", [sys.executable, "scripts/eval_physics.py"]),
    ("eval_precedent", [sys.executable, "scripts/eval_precedent.py"]),
    ("eval_crossmodal", [sys.executable, "scripts/eval_crossmodal.py"]),
    ("eval_savings_levers", [sys.executable, "scripts/eval_savings_levers.py"]),
    ("trial_power", [sys.executable, "scripts/trial_power.py"]),
    ("compare_models", [sys.executable, "scripts/compare_models.py"]),  # needs optional xgboost and lightgbm
]


def main():
    if not (config.DATA_DIR / "daily_production.parquet").exists():
        sys.exit(f"DATA_DIR={config.DATA_DIR} does not contain daily_production.parquet")
    out = config.WORK_DIR / "reports"
    out.mkdir(parents=True, exist_ok=True)
    have_boost = all(importlib.util.find_spec(m) for m in ("xgboost", "lightgbm"))
    results = []
    for name, cmd in STEPS:
        if name == "compare_models" and not have_boost:
            results.append((name, "skipped (pip install xgboost lightgbm to run it)", 0.0))
            continue
        t0 = time.time()
        print(f"--> {name} ...", flush=True)
        p = subprocess.run(cmd, cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True)
        (out / f"{name}.txt").write_text(p.stdout + ("\n[stderr]\n" + p.stderr if p.stderr else ""), encoding="utf-8")
        results.append((name, "ok" if p.returncode == 0 else f"FAILED (exit {p.returncode})", time.time() - t0))
        if name == "tests" and p.returncode != 0:
            break
    print("\nSummary (full output in " + str(out) + "):")
    for name, status, secs in results:
        print(f"  {name:22s} {status:45s} {secs:6.0f}s")
    sys.exit(0 if all(s in ("ok",) or s.startswith("skipped") for _, s, _ in results) else 1)


if __name__ == "__main__":
    main()
