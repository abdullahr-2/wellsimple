"""Backtest of the precedent engine: given a repair note, how well do the outcomes
of the most similar *earlier* jobs (on other wells) predict how long the fix lasts?

Usage: DATA_DIR=... python scripts/eval_precedent.py [tfidf|sentence|both]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from wellsimple import data, notes

CUTOFF = pd.Timestamp("2026-01-01")
K = 10


def evaluate(name, encoder, rep):
    mem = notes.WellMemory(encoder).build(rep, fit_before=CUTOFF)
    j = mem.jobs
    start = j["start_date"].values
    uwi = j["uwi"].values
    life = j["life_days"].values
    tr = start < np.datetime64(CUTOFF)
    te = (~tr) & np.isfinite(life)  # only test jobs whose outcome was observed
    qi = np.where(te)[0]
    train_med = np.nanmedian(life[tr])
    pred, naive_same_well = [], []
    for i in qi:
        sims = mem.vecs @ mem.vecs[i]
        ok = (start < start[i]) & (uwi != uwi[i]) & np.isfinite(life)  # earlier, other wells
        sims = np.where(ok, sims, -np.inf)
        top = np.argpartition(-sims, K)[:K]
        pred.append(np.median(life[top]))
        same = np.where((uwi == uwi[i]) & (start < start[i]) & np.isfinite(life))[0]
        naive_same_well.append(np.median(life[same]) if len(same) else train_med)
    pred = np.array(pred); actual = life[qi]; sw = np.array(naive_same_well)
    mae = lambda p: np.mean(np.abs(np.log1p(p) - np.log1p(actual)))
    print(f"{name:22s} n={len(qi)}  log-MAE: precedent {mae(pred):.3f} | global median {mae(np.full(len(actual), train_med)):.3f}"
          f" | well's own history {mae(sw):.3f}   Spearman precedent {spearmanr(pred, actual)[0]:.3f}"
          f" | own history {spearmanr(sw, actual)[0]:.3f}")
    return mem


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "tfidf"
    rep = data.add_job_outcomes(data.load_jobs())
    if which in ("tfidf", "both"):
        evaluate("TF-IDF + SVD", notes.TfidfEncoder(), rep)
    if which in ("sentence", "both"):
        evaluate("MiniLM sentence", notes.SentenceEncoder(), rep)


if __name__ == "__main__":
    main()
