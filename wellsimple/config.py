"""Central settings. The dataset location always comes from the environment so the
restricted competition data is never copied into the repository."""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).expanduser()
WORK_DIR = Path(os.environ.get("WORK_DIR", "artifacts")).expanduser()

DAILY = DATA_DIR / "daily_production.parquet"
JOBS = DATA_DIR / "well_jobs.parquet"
FAILURES = DATA_DIR / "production_failures.parquet"

# Failures in the log are essentially all in 2025-2026, so time splits live there.
TRAIN_END = "2026-01-01"

# Placeholder sensor codes found in the data (documented in the handbook).
PRESSURE_PLACEHOLDER = 99999
