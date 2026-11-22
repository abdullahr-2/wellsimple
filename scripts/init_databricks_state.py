"""Initialize the application state from an exported D1 snapshot once."""
import json
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem

state = json.loads(Path("artifacts/databricks-import/state.json").read_text(encoding="utf-8"))
for key in ("crews", "assignments", "vectors"):
    if isinstance(state[key], dict) and "value" in state[key]:
        state[key] = state[key]["value"]
payload = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
client = WorkspaceClient(profile="wellsimple")
refresh = "--refresh" in sys.argv
if refresh:
    current = client.statement_execution.execute_statement(
        warehouse_id="7a37fcfd214d743a",
        statement="SELECT revision FROM workspace.wellsimple.app_state WHERE id=1",
        wait_timeout="30s",
    )
    if current.status.state.value != "SUCCEEDED" or len(current.result.data_array) != 1:
        raise RuntimeError("Expected one application state row")
    revision = current.result.data_array[0][0]
    sql = ("UPDATE workspace.wellsimple.app_state SET payload=:payload, revision=revision+1 "
           "WHERE id=1 AND revision=:revision")
    parameters = [StatementParameterListItem(name="payload", value=payload, type="STRING"),
                  StatementParameterListItem(name="revision", value=revision, type="BIGINT")]
else:
    sql = ("INSERT INTO workspace.wellsimple.app_state "
           "SELECT 1, 0, :payload WHERE NOT EXISTS "
           "(SELECT 1 FROM workspace.wellsimple.app_state WHERE id=1)")
    parameters = [StatementParameterListItem(name="payload", value=payload, type="STRING")]
result = client.statement_execution.execute_statement(
    warehouse_id="7a37fcfd214d743a",
    statement=sql,
    parameters=parameters,
    wait_timeout="30s",
)
while result.status.state.value in ("PENDING", "RUNNING"):
    time.sleep(2)
    result = client.statement_execution.get_statement(result.statement_id)
if result.status.state.value != "SUCCEEDED":
    raise RuntimeError(result.status.error)
if refresh and (not result.result or result.result.data_array != [["1"]]):
    raise RuntimeError("Application state changed during migration")
print("Initialized application state.")
