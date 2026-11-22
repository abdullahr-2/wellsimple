"""Print the serverless Python environment (versions and whether key imports work)."""
import importlib
import sys
import traceback

print("python", sys.version.split()[0])
for m in ("numpy", "pandas", "pyarrow", "sklearn", "scipy", "joblib"):
    try:
        mod = importlib.import_module(m)
        print(f"{m:8s} {getattr(mod, '__version__', '?')}")
    except Exception:
        print(f"{m:8s} IMPORT FAILED:", traceback.format_exc().strip().splitlines()[-1])
