"""Does Databricks Vector Search return the same precedents as exact search?

Uses the vectors stored in workspace.wellsimple_pipeline.gold_repair_notes for both sides, so the
comparison measures Vector Search itself (not differences between library versions). Samples real
notes as queries with the app's filters (earlier jobs only, other wells only) and compares the top
10 with exact cosine search. Read-only.

Usage: python scripts/check_vector_search.py --profile <databricks-profile> --warehouse <sql-warehouse-id>
"""
import argparse
import json
import time

import numpy as np
from databricks.sdk import WorkspaceClient

TABLE = "workspace.wellsimple_pipeline.gold_repair_notes"
INDEX = "workspace.wellsimple_pipeline.repair_notes_index"


def fetch_all(w, warehouse, sql):
    r = w.statement_execution.execute_statement(warehouse_id=warehouse, statement=sql, wait_timeout="50s")
    while r.status.state.value in ("PENDING", "RUNNING"):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state.value != "SUCCEEDED":
        raise RuntimeError(r.status.error.message if r.status.error else r.status.state.value)
    rows, res = list(r.result.data_array or []), r.result
    while res.next_chunk_index:
        res = w.statement_execution.get_statement_result_chunk_n(r.statement_id, res.next_chunk_index)
        rows += res.data_array or []
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="wellsimple")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--queries", type=int, default=300)
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    rows = fetch_all(w, a.warehouse, f"SELECT note_id, uwi, start_day, to_json(embedding) FROM {TABLE}")
    ids = np.array([r[0] for r in rows])
    uwi = np.array([r[1] for r in rows], dtype=object)
    day = np.array([int(r[2]) for r in rows])
    V = np.array([json.loads(r[3]) for r in rows], dtype="float32")
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
    print(f"loaded {len(ids):,} stored note vectors ({V.shape[1]} dims)")

    rng = np.random.default_rng(0)
    recalls, lat = [], []
    for i in rng.choice(len(ids), a.queries, replace=False):
        q = V[i]
        sims = V @ q
        ok = (day < day[i]) & (uwi != uwi[i])
        if ok.sum() < 10:
            continue
        s = np.where(ok, sims, -np.inf)
        top = np.argsort(-s)[:10]
        cutoff = s[top[-1]] - 1e-5               # ties at 10th place are interchangeable
        t0 = time.perf_counter()
        res = w.vector_search_indexes.query_index(
            index_name=INDEX, columns=["note_id"], query_vector=q.tolist(), num_results=10,
            filters_json=json.dumps({"start_day <": int(day[i]), "uwi NOT": str(uwi[i])}))
        lat.append(time.perf_counter() - t0)
        got = [row[0] for row in (res.result.data_array or [])]
        pos = {v: k for k, v in enumerate(ids)}
        exact_ids = set(ids[top])
        hits = sum(1 for g in got if g in exact_ids or (g in pos and ok[pos[g]] and sims[pos[g]] >= cutoff))
        recalls.append(hits / 10)
    print(f"Databricks Vector Search vs exact search, {len(recalls)} real queries with the app's filters:")
    print(f"  recall@10 {np.mean(recalls):.1%} (min {np.min(recalls):.0%}) | median query {np.median(lat) * 1000:.0f} ms "
          f"(includes the network round trip from this machine)")


if __name__ == "__main__":
    main()
