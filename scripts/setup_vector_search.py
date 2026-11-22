"""Create (or reuse) the Databricks Vector Search endpoint and the repair-notes index.

The index syncs from workspace.wellsimple_pipeline.gold_repair_notes (change data feed on) and
uses the pipeline's own 100-dimension note vectors, so search results match the app's encoder.
Safe to rerun: existing endpoint and index are reused, and a sync is triggered.

Usage: python scripts/setup_vector_search.py --profile <databricks-profile>
"""
import argparse
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (DeltaSyncVectorIndexSpecRequest, EmbeddingVectorColumn,
                                                 EndpointType, PipelineType, VectorIndexType)

ENDPOINT = "wellsimple-vs"
SOURCE = "workspace.wellsimple_pipeline.gold_repair_notes"
INDEX = "workspace.wellsimple_pipeline.repair_notes_index"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="wellsimple")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)

    names = [e.name for e in w.vector_search_endpoints.list_endpoints()]
    if ENDPOINT not in names:
        print(f"creating endpoint {ENDPOINT} (this can take several minutes) ...", flush=True)
        w.vector_search_endpoints.create_endpoint(name=ENDPOINT, endpoint_type=EndpointType.STANDARD)
    t0 = time.time()
    while True:
        e = w.vector_search_endpoints.get_endpoint(ENDPOINT)
        state = e.endpoint_status.state.value if e.endpoint_status and e.endpoint_status.state else "UNKNOWN"
        if state == "ONLINE":
            print(f"endpoint {ENDPOINT} online after {time.time() - t0:.0f}s", flush=True)
            break
        if state in ("OFFLINE", "RED_STATE") or "FAIL" in state:
            raise SystemExit(f"endpoint state {state}: {e.endpoint_status.message}")
        time.sleep(20)

    try:
        w.vector_search_indexes.get_index(INDEX)
        print(f"index {INDEX} exists; triggering a sync", flush=True)
        w.vector_search_indexes.sync_index(INDEX)
    except Exception:
        print(f"creating index {INDEX} from {SOURCE} ...", flush=True)
        w.vector_search_indexes.create_index(
            name=INDEX, endpoint_name=ENDPOINT, primary_key="note_id", index_type=VectorIndexType.DELTA_SYNC,
            delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
                source_table=SOURCE, pipeline_type=PipelineType.TRIGGERED,
                embedding_vector_columns=[EmbeddingVectorColumn(name="embedding", embedding_dimension=100)],
                columns_to_sync=["note_id", "uwi", "start_day", "start_date", "job_type", "text", "cost", "life_days"]))
    t0 = time.time()
    while True:
        idx = w.vector_search_indexes.get_index(INDEX)
        st = idx.status
        ready = bool(st and st.ready)
        n = st.indexed_row_count if st else None
        if ready:
            print(f"index ready after {time.time() - t0:.0f}s with {n} rows", flush=True)
            break
        msg = (st.message or "")[:120] if st else ""
        print(f"  waiting for index ({time.time() - t0:.0f}s): rows {n} {msg}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
