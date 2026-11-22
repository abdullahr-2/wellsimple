"""Compare the pipeline's app tables with the app's current tables in Databricks.

Checks that workspace.wellsimple_pipeline.app_{facts,wells,terms} can replace
workspace.wellsimple.{facts,wells,terms}: same wells, same pilot arms, same facts keys and
model shape, same vocabulary, and how far the risk scores differ. Read-only.

Usage: python scripts/verify_app_tables.py --profile <databricks-profile> --warehouse <id>
"""
import argparse
import json
import time

from databricks.sdk import WorkspaceClient


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="wellsimple")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--app", default="workspace.wellsimple")
    ap.add_argument("--pipeline", default="workspace.wellsimple_pipeline")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)

    def q(sql):
        r = w.statement_execution.execute_statement(warehouse_id=a.warehouse, statement=sql, wait_timeout="50s")
        while r.status.state.value in ("PENDING", "RUNNING"):
            time.sleep(2)
            r = w.statement_execution.get_statement(r.statement_id)
        if r.status.state.value != "SUCCEEDED":
            raise RuntimeError(r.status.error.message if r.status.error else r.status.state.value)
        return r.result.data_array or [] if r.result else []

    A, P = a.app, a.pipeline
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'ok' if cond else 'DIFF'}] {name} {detail}")

    print("wells")
    na, np_ = (int(q(f"SELECT COUNT(*) FROM {t}")[0][0]) for t in (f"{A}.wells", f"{P}.app_wells"))
    check("row count", na == np_, f"app {na} vs pipeline {np_}")
    only = q(f"SELECT COUNT(*) FROM (SELECT uwi FROM {A}.wells EXCEPT SELECT uwi FROM {P}.app_wells)")[0][0]
    only2 = q(f"SELECT COUNT(*) FROM (SELECT uwi FROM {P}.app_wells EXCEPT SELECT uwi FROM {A}.wells)")[0][0]
    check("same wells", only == "0" and only2 == "0", f"(only in app: {only}, only in pipeline: {only2})")
    arm_diff = q(f"SELECT COUNT(*) FROM {A}.wells a JOIN {P}.app_wells p USING (uwi) WHERE NOT (a.arm <=> p.arm)")[0][0]
    check("same pilot arms", arm_diff == "0", f"({arm_diff} wells differ)")
    d = q(f"""SELECT MAX(ABS(CAST(get_json_object(a.listing,'$.p_repair') AS DOUBLE) -
                         CAST(get_json_object(p.listing,'$.p_repair') AS DOUBLE))),
                     AVG(ABS(CAST(get_json_object(a.listing,'$.p_repair') AS DOUBLE) -
                         CAST(get_json_object(p.listing,'$.p_repair') AS DOUBLE)))
              FROM {A}.wells a JOIN {P}.app_wells p USING (uwi)""")[0]
    check("risk scores", float(d[0]) < 1e-9, f"(max difference {float(d[0]):.2e}, mean {float(d[1]):.2e})")

    print("facts")
    ka = {r[0] for r in q(f"SELECT key FROM {A}.facts")}
    kp = {r[0] for r in q(f"SELECT key FROM {P}.app_facts")}
    check("same keys", ka == kp, f"(app {len(ka)}, pipeline {len(kp)}; only in app: {sorted(ka - kp)[:5]}, only in pipeline: {sorted(kp - ka)[:5]})")
    ma = json.loads(q(f"SELECT value FROM {A}.facts WHERE key='model'")[0][0])
    mp = json.loads(q(f"SELECT value FROM {P}.app_facts WHERE key='model'")[0][0])
    check("same model features and tree count", ma["features"] == mp["features"] and ma["trees"] == mp["trees"],
          f"(features {len(ma['features'])} vs {len(mp['features'])}, trees {ma['trees']} vs {mp['trees']})")

    print("terms")
    ta, tp = (int(q(f"SELECT COUNT(*) FROM {t}")[0][0]) for t in (f"{A}.terms", f"{P}.app_terms"))
    check("vocabulary size", ta == tp, f"app {ta} vs pipeline {tp}")

    print("\nRESULT:", "the pipeline tables can replace the app tables" if ok else "differences found (see DIFF lines)")


if __name__ == "__main__":
    main()
