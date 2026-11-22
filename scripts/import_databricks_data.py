"""Create Databricks tables from the private parquet migration files."""
import time

from databricks.sdk import WorkspaceClient

client = WorkspaceClient(profile="wellsimple")
warehouse = "7a37fcfd214d743a"

for table in ("facts", "wells", "terms"):
    statement = (
        f"CREATE TABLE IF NOT EXISTS workspace.wellsimple.{table} "
        f"AS SELECT * FROM parquet.`/Volumes/workspace/wellsimple/migration/import/{table}.parquet`"
    )
    result = client.statement_execution.execute_statement(
        statement=statement, warehouse_id=warehouse, wait_timeout="30s"
    )
    while result.status.state.value in ("PENDING", "RUNNING"):
        time.sleep(3)
        result = client.statement_execution.get_statement(result.statement_id)
    if result.status.state.value != "SUCCEEDED":
        raise RuntimeError(f"{table}: {result.status.error}")
    print(f"Created {table}")
