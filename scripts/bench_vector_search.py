"""Vector database vs exact search: same answers? how does it scale?

A. Real notes: build Well Memory in Chroma, measure build time and reopen time, and check that
   its top 10 precedents match exact search (recall@10) on sampled real queries with the same
   filters the app uses (earlier jobs only, other wells only).
B. Scale: query latency and recall for exact numpy search vs Chroma on random 100-dimension
   vectors (a speed benchmark only; the vectors are synthetic, not data).

Usage: DATA_DIR=... python scripts/bench_vector_search.py
"""
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from wellsimple import data, notes, vectorstore


def timed(f):
    t0 = time.perf_counter()
    r = f()
    return r, time.perf_counter() - t0


def main():
    tmp = Path(tempfile.mkdtemp(prefix="wm_bench_"))
    try:
        rep = data.add_job_outcomes(data.load_jobs())
        exact = notes.WellMemory(notes.TfidfEncoder()).build(rep)
        db, t_build = timed(lambda: notes.WellMemory(notes.TfidfEncoder(), vectorstore.ChromaIndex(tmp / "real")).build(rep))
        _, t_reopen = timed(lambda: notes.WellMemory(notes.TfidfEncoder(), vectorstore.ChromaIndex(tmp / "real")).build(rep))
        print(f"== A. Real notes ({len(exact.jobs):,}) in Chroma: first build {t_build:.1f} s, reopen with stored index {t_reopen:.1f} s")
        rng = np.random.default_rng(0)
        sample = rng.choice(len(exact.jobs), 300, replace=False)
        rec, lat_e, lat_d = [], [], []
        for i in sample:
            r = exact.jobs.iloc[i]
            a, te = timed(lambda: exact.search(r["text"], k=10, before=r["start_date"], exclude_uwi=r["uwi"]))
            b, td = timed(lambda: db.search(r["text"], k=10, before=r["start_date"], exclude_uwi=r["uwi"]))
            if a:
                key = lambda p: (p.uwi, str(p.start_date), p.text[:60])
                cutoff = min(p.similarity for p in a) - 1e-6  # ties at the 10th place are interchangeable
                rec.append(sum(1 for p in b if key(p) in {key(x) for x in a} or p.similarity >= cutoff) / len(a))
            lat_e.append(te); lat_d.append(td)
        print(f"   recall@10 vs exact search: {np.mean(rec):.1%} (min {np.min(rec):.0%}) over {len(rec)} real queries with filters")
        print(f"   median search incl. encoding: exact {np.median(lat_e) * 1000:.1f} ms | Chroma {np.median(lat_d) * 1000:.1f} ms")

        print("== B. Scale (synthetic 100-dim vectors, speed only)")
        for n in (100_000, 500_000):
            v = rng.standard_normal((n, 100)).astype("float32")
            v /= np.linalg.norm(v, axis=1, keepdims=True)
            ids = [f"job-{i}" for i in range(n)]
            uwis = np.array([f"w{i % 3000}" for i in range(n)], dtype=object)
            days = 19000 + (np.arange(n) % 2000)
            mem = vectorstore.InMemoryIndex(); mem.add(ids, v, uwis, days)
            ch = vectorstore.ChromaIndex(tmp / f"s{n}"); ch.reset("bench")
            _, t_ins = timed(lambda: ch.add(ids, v, uwis, days))
            qs = rng.choice(n, 50, replace=False)
            rc, te_, td_ = [], [], []
            for q in qs:
                a, te = timed(lambda: mem.query(v[q], 10, 20500, f"w{q % 3000}"))
                b, td = timed(lambda: ch.query(v[q], 10, 20500, f"w{q % 3000}"))
                rc.append(len({x[0] for x in a} & {x[0] for x in b}) / 10); te_.append(te); td_.append(td)
            print(f"   {n:>9,} vectors: exact {np.median(te_) * 1000:6.1f} ms | Chroma {np.median(td_) * 1000:6.1f} ms "
                  f"| Chroma recall@10 {np.mean(rc):.1%} | Chroma insert {t_ins:.0f} s (once; persisted after)")
            del ch, mem, v
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
