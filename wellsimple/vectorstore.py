"""Vector store backends for Well Memory.

Both backends hold one vector per repair note with two filterable fields (well id, start
day) and answer the same query: the k most similar notes, optionally only earlier ones and
never from the same well.

- InMemoryIndex: exact cosine search with numpy. No dependencies; used in tests and backtests.
- ChromaIndex:   Chroma, an embedded vector database persisted to disk. No server to run; the
                 index survives restarts, so it is not rebuilt each time, and crew notes are
                 stored in it permanently. Production path: the same interface on Databricks
                 Vector Search or Postgres with pgvector, which several app servers can share.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def to_day(ts) -> int:
    """Days since 1970-01-01, the form both backends filter on."""
    return int(pd.Timestamp(ts).value // 86_400_000_000_000)


class InMemoryIndex:
    persistent = False

    def __init__(self):
        self.ids: list[str] = []
        self.pos: dict[str, int] = {}
        self.vecs = np.zeros((0, 0), dtype="float32")
        self.uwi = np.array([], dtype=object)
        self.day = np.array([], dtype=np.int64)

    def __len__(self):
        return len(self.ids)

    def is_current(self, fingerprint: str) -> bool:
        return False

    def reset(self, fingerprint: str) -> None:
        self.__init__()

    def add(self, ids, vecs, uwis, days, kinds=None) -> None:
        """Insert or replace (upsert) by id."""
        vecs = np.asarray(vecs, dtype="float32")
        if self.vecs.size == 0:
            self.vecs = np.zeros((0, vecs.shape[1]), dtype="float32")
        new_rows = []
        for i, vid in enumerate(ids):
            if vid in self.pos:
                p = self.pos[vid]
                self.vecs[p], self.uwi[p], self.day[p] = vecs[i], uwis[i], days[i]
            else:
                new_rows.append(i)
        if new_rows:
            start = len(self.ids)
            for n, i in enumerate(new_rows):
                self.ids.append(ids[i])
                self.pos[ids[i]] = start + n
            self.vecs = np.vstack([self.vecs, vecs[new_rows]])
            self.uwi = np.concatenate([self.uwi, np.asarray(uwis, dtype=object)[new_rows]])
            self.day = np.concatenate([self.day, np.asarray(days, dtype=np.int64)[new_rows]])

    def delete_kind(self, kind: str) -> None:
        keep = [i for i, vid in enumerate(self.ids) if not vid.startswith(kind + "-")]
        self.ids = [self.ids[i] for i in keep]
        self.pos = {vid: n for n, vid in enumerate(self.ids)}
        self.vecs, self.uwi, self.day = self.vecs[keep], self.uwi[keep], self.day[keep]

    def query(self, vec, k: int, before_day: int | None = None, exclude_uwi: str | None = None):
        if not self.ids:
            return []
        sims = self.vecs @ np.asarray(vec, dtype="float32")
        ok = np.ones(len(sims), dtype=bool)
        if before_day is not None:
            ok &= self.day < before_day
        if exclude_uwi is not None:
            ok &= self.uwi != exclude_uwi
        sims = np.where(ok, sims, -np.inf)
        k = min(k, int(ok.sum()))
        if k <= 0:
            return []
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [(self.ids[i], float(sims[i])) for i in top]


class ChromaIndex:
    persistent = True
    NAME = "well_memory_notes"

    def __init__(self, path):
        import chromadb
        from chromadb.config import Settings

        self.client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
        self.col = self.client.get_or_create_collection(self.NAME, configuration={"hnsw": {"space": "cosine"}})

    def __len__(self):
        return self.col.count()

    def is_current(self, fingerprint: str) -> bool:
        """True if the stored index was built from exactly the same notes and encoder."""
        return (self.col.metadata or {}).get("fingerprint") == fingerprint and self.col.count() > 0

    def reset(self, fingerprint: str) -> None:
        try:
            self.client.delete_collection(self.NAME)
        except Exception:
            pass
        self.col = self.client.create_collection(self.NAME, configuration={"hnsw": {"space": "cosine"}},
                                                 metadata={"fingerprint": fingerprint})

    def add(self, ids, vecs, uwis, days, kinds=None) -> None:
        vecs = np.asarray(vecs, dtype="float32")
        step = 5000
        for s in range(0, len(ids), step):
            sl = slice(s, s + step)
            self.col.upsert(ids=list(ids[sl]), embeddings=vecs[sl].tolist(),
                            metadatas=[{"uwi": str(u), "day": int(d)} for u, d in zip(uwis[sl], days[sl])])

    def delete_kind(self, kind: str) -> None:
        got = self.col.get(include=[])
        stale = [i for i in got["ids"] if i.startswith(kind + "-")]
        if stale:
            self.col.delete(ids=stale)

    def query(self, vec, k: int, before_day: int | None = None, exclude_uwi: str | None = None):
        conds = []
        if before_day is not None:
            conds.append({"day": {"$lt": int(before_day)}})
        if exclude_uwi is not None:
            conds.append({"uwi": {"$ne": str(exclude_uwi)}})
        where = None if not conds else (conds[0] if len(conds) == 1 else {"$and": conds})
        n = min(k, self.col.count())
        if n <= 0:
            return []
        r = self.col.query(query_embeddings=[np.asarray(vec, dtype="float32").tolist()], n_results=n, where=where,
                           include=["distances"])
        return [(i, 1.0 - float(d)) for i, d in zip(r["ids"][0], r["distances"][0])]


def make_index(backend: str, path=None):
    """'memory' or 'chroma'. Chroma needs a folder to persist to. If Chroma is not installed,
    fall back to exact in-memory search, which gives the same answers."""
    if backend == "chroma":
        try:
            return ChromaIndex(path)
        except ImportError:
            print("chromadb is not installed: using exact in-memory search instead (pip install chromadb)")
    return InMemoryIndex()
