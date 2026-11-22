"""Prepare the existing private hosted-data export for Databricks import."""
import sqlite3
from pathlib import Path

import pandas as pd

work = Path("artifacts")
output = work / "databricks-import"
output.mkdir(parents=True, exist_ok=True)

with sqlite3.connect(":memory:") as db:
    db.executescript((work / "competition-import.sql").read_text(encoding="utf-8"))
    for table in ("facts", "wells", "terms"):
        frame = pd.read_sql_query(f"SELECT * FROM {table}", db)
        for column in frame:
            frame[column] = frame[column].astype("string")
        frame.to_parquet(output / f"{table}.parquet", index=False)
        print(f"{table}: {len(frame)} rows")
