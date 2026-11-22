"""Both vector store backends must give the same answers, filter correctly and persist."""
import numpy as np
import pandas as pd
import pytest

from wellsimple import notes, vectorstore

chromadb = pytest.importorskip("chromadb")


def _data(n=400, d=16, seed=0):
    rng = np.random.default_rng(seed)
    v = rng.standard_normal((n, d)).astype("float32")
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    ids = [f"job-{i}" for i in range(n)]
    uwis = np.array([f"w{i % 20}" for i in range(n)], dtype=object)
    days = np.arange(n) + 19000
    return ids, v, uwis, days


def test_chroma_matches_exact_search_with_filters(tmp_path):
    ids, v, uwis, days = _data()
    mem, db = vectorstore.InMemoryIndex(), vectorstore.ChromaIndex(tmp_path / "vec")
    db.reset("fp")
    for idx in (mem, db):
        idx.add(ids, v, uwis, days)
    for q in range(0, 400, 37):
        for before, excl in ((None, None), (19300, None), (None, "w3"), (19250, "w5")):
            a = mem.query(v[q], 10, before, excl)
            b = db.query(v[q], 10, before, excl)
            assert [x[0] for x in a] == [x[0] for x in b]
            assert np.allclose([x[1] for x in a], [x[1] for x in b], atol=1e-4)
            got = {i: k for k, i in enumerate(ids)}
            assert all(days[got[i]] < before for i, _ in b) if before else True
            assert all(uwis[got[i]] != excl for i, _ in b) if excl else True


def test_chroma_persists_and_upsert_does_not_duplicate(tmp_path):
    ids, v, uwis, days = _data(50)
    db = vectorstore.ChromaIndex(tmp_path / "vec")
    db.reset("fp1")
    db.add(ids, v, uwis, days)
    db.add(ids[:5], v[:5], uwis[:5], days[:5])          # same ids again
    assert len(db) == 50
    reopened = vectorstore.ChromaIndex(tmp_path / "vec")
    assert len(reopened) == 50 and reopened.is_current("fp1") and not reopened.is_current("fp2")
    reopened.add(["crew-1"], v[:1], np.array(["w1"], dtype=object), [19999])
    reopened.delete_kind("crew")
    assert len(reopened) == 50


def _jobs():
    rows = []
    for i in range(8):
        rows.append(("a%d" % i, "broken polish rod replaced rod string", 30.0 + i, 4000.0))
        rows.append(("b%d" % i, "pump change new rotor stator installed", 200.0 + i, 20000.0))
    df = pd.DataFrame(rows, columns=["uwi", "text", "life_days", "cost"])
    df["start_date"] = pd.Timestamp("2025-01-01") + pd.to_timedelta(np.arange(len(df)), unit="D")
    df["censored"] = False
    return df


def test_well_memory_gives_same_precedents_on_both_backends_and_reuses_the_stored_index(tmp_path):
    jobs = _jobs()
    mem = notes.WellMemory(notes.TfidfEncoder(dims=3)).build(jobs)
    db = notes.WellMemory(notes.TfidfEncoder(dims=3), vectorstore.ChromaIndex(tmp_path / "v")).build(jobs)
    for q in ("broken rod string", "pump rotor stator"):
        # notes here are identical copies, so ties are interchangeable: compare scores and exclusions
        a = mem.search(q, k=6, exclude_uwi="a0")
        b = db.search(q, k=6, exclude_uwi="a0")
        assert sorted(round(p.similarity, 4) for p in a) == sorted(round(p.similarity, 4) for p in b)
        assert all(p.uwi != "a0" for p in b)
    db.add_job("zz", "polish rod broke at the clamp", vid="crew-7")
    db.add_job("zz", "polish rod broke at the clamp", vid="crew-7")  # replayed: stored once
    assert len(db.index) == len(jobs) + 1
    again = notes.WellMemory(notes.TfidfEncoder(dims=3), vectorstore.ChromaIndex(tmp_path / "v")).build(jobs)
    assert len(again.index) == len(jobs)  # stored index reused; crew notes removed until replayed from the app


def test_make_index_falls_back_to_exact_search_without_chroma(monkeypatch, tmp_path):
    import builtins
    real_import = builtins.__import__

    def no_chroma(name, *a, **k):
        if name.startswith("chromadb"):
            raise ImportError("no chromadb")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_chroma)
    idx = vectorstore.make_index("chroma", tmp_path / "v")
    assert isinstance(idx, vectorstore.InMemoryIndex)
