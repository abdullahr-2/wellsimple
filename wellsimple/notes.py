"""Precedent retrieval over crew notes ("Well Memory").

Each repair job becomes a record: note text, cost, and how many days the fix
lasted (days until the next repair job on that well). Retrieval is nearest
neighbours in an embedding space, and every answer is computed from real past
jobs. No generative model writes or invents anything.

Two interchangeable encoders:
 - TfidfEncoder: no model download, works anywhere (also the baseline)
 - SentenceEncoder: local open-source sentence embeddings (needs sentence-transformers)
"""
from __future__ import annotations

import hashlib

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


class TfidfEncoder:
    def __init__(self, dims: int = 100):
        self.tfidf = TfidfVectorizer(min_df=3, stop_words="english", sublinear_tf=True, max_features=20000)
        self.svd = TruncatedSVD(dims, random_state=0)

    def fit(self, texts):
        self.svd.fit(self.tfidf.fit_transform(texts))
        return self

    def encode(self, texts) -> np.ndarray:
        return normalize(self.svd.transform(self.tfidf.transform(texts)))


class SentenceEncoder:
    def __init__(self, name: str = "sentence-transformers/all-MiniLM-L6-v2", max_chars: int = 1500):
        from sentence_transformers import SentenceTransformer  # imported lazily

        self.model = SentenceTransformer(name, device="cpu")
        self.max_chars = max_chars

    def fit(self, texts):  # nothing to fit; kept for interface parity
        return self

    def encode(self, texts) -> np.ndarray:
        clipped = [t[: self.max_chars] for t in texts]
        return self.model.encode(clipped, batch_size=64, normalize_embeddings=True, show_progress_bar=False)


@dataclass
class Precedent:
    uwi: str
    start_date: pd.Timestamp
    similarity: float
    text: str
    cost: float
    life_days: float
    censored: bool


class WellMemory:
    """Repair notes as vectors, each with its job's outcome, in a vector store
    (exact in-memory search by default, or the Chroma vector database)."""

    def __init__(self, encoder, index=None):
        from .vectorstore import InMemoryIndex

        self.encoder = encoder
        self.index = index if index is not None else InMemoryIndex()
        self.jobs: pd.DataFrame | None = None
        self.row_of: dict[str, int] = {}

    @property
    def vecs(self) -> np.ndarray:
        """Note vectors (in-memory backend only)."""
        return self.index.vecs

    def _fingerprint(self, texts: list[str]) -> str:
        h = hashlib.sha1()
        h.update(f"{type(self.encoder).__name__}|{getattr(self.encoder, 'svd', None) and self.encoder.svd.n_components}|".encode())
        for t in texts:
            h.update(t.encode("utf-8", "ignore"))
            h.update(b"\x00")
        return h.hexdigest()

    def build(self, jobs: pd.DataFrame, fit_before: pd.Timestamp | None = None) -> "WellMemory":
        """`jobs` must come from data.add_job_outcomes (repair jobs with life_days).

        `fit_before` restricts what the encoder learns its vocabulary from, so a
        backtest never sees text from the period it is tested on. A persistent store
        is only re-written when the notes or the encoder have changed.
        """
        from .vectorstore import to_day

        j = jobs[jobs["text"].str.len() > 5].reset_index(drop=True)
        j["vid"] = [f"job-{i}" for i in range(len(j))]
        self.jobs = j
        self.row_of = {v: i for i, v in enumerate(j["vid"])}
        fit_texts = j["text"] if fit_before is None else j.loc[j["start_date"] < fit_before, "text"]
        self.encoder.fit(fit_texts.tolist())  # deterministic, so stored vectors stay consistent
        fp = self._fingerprint(j["text"].tolist() + ["|fit|"] + fit_texts.tolist())
        if self.index.persistent and self.index.is_current(fp):
            self.index.delete_kind("crew")  # crew notes are replayed from the app's store
            return self
        self.index.reset(fp)
        self.index.add(j["vid"].tolist(), self.encoder.encode(j["text"].tolist()).astype("float32"),
                       j["uwi"].to_numpy(), [to_day(d) for d in j["start_date"]])
        return self

    def add_job(self, uwi: str, text: str, cost: float | None = None,
                start_date: pd.Timestamp | None = None, vid: str | None = None) -> None:
        """Add a crew note to the memory. Its outcome is unknown until the next job on the
        well arrives. `vid` makes the insert idempotent (the same note is stored once)."""
        from .vectorstore import to_day

        vid = vid or f"crew-new-{len(self.jobs)}"
        when = start_date or pd.Timestamp.now().normalize()
        row = {c: np.nan for c in self.jobs.columns}
        row.update(uwi=uwi, text=text.lower(), cost=cost if cost is not None else np.nan,
                   start_date=when, life_days=np.nan, censored=True, vid=vid)
        if vid in self.row_of:
            self.jobs.loc[self.row_of[vid], list(row)] = list(row.values())
        else:
            self.row_of[vid] = len(self.jobs)
            self.jobs = pd.concat([self.jobs, pd.DataFrame([row])], ignore_index=True)
        self.index.add([vid], self.encoder.encode([text.lower()]).astype("float32"), np.array([uwi], dtype=object),
                       [to_day(when)])

    def search(
        self,
        query: str,
        k: int = 10,
        before: pd.Timestamp | None = None,
        exclude_uwi: str | None = None,
    ) -> list[Precedent]:
        """Nearest past jobs. `before` keeps only earlier jobs (no future leakage)."""
        from .vectorstore import to_day

        q = self.encoder.encode([query.lower()])[0].astype("float32")
        hits = self.index.query(q, k, None if before is None else to_day(before), exclude_uwi)
        out = []
        for vid, sim in hits:
            i = self.row_of.get(vid)
            if i is None:  # a vector with no matching note (stale entry): skip it
                continue
            r = self.jobs.iloc[i]
            out.append(Precedent(r["uwi"], r["start_date"], float(sim), r["text"],
                                 r["cost"], r["life_days"], bool(r["censored"])))
        return out


def summarize(precedents: list[Precedent]) -> dict:
    """Outcome statistics over retrieved precedents (observed lifetimes only)."""
    life = np.array([p.life_days for p in precedents if np.isfinite(p.life_days)])
    cost = np.array([p.cost for p in precedents if np.isfinite(p.cost)])
    return {
        "n": len(precedents),
        "median_life_days": float(np.median(life)) if len(life) else None,
        "life_p25": float(np.percentile(life, 25)) if len(life) else None,
        "life_p75": float(np.percentile(life, 75)) if len(life) else None,
        "median_cost": float(np.median(cost)) if len(cost) else None,
        # cost of the fix per day it lasted, the headline comparison metric
        "cost_per_day_of_life": float(np.median(cost) / np.median(life)) if len(life) and len(cost) else None,
    }
