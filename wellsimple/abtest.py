"""A/B pilot machinery: who gets enrolled, how they are randomized, how the result is read.

The plan is fixed before any outcome exists (pre-registration):
  population  producing wells that had a repeat repair (a repair job within 30 days of the
              previous repair on the same well) in the 12 months before enrollment
  arms        "system": the manager portal recommends and tracks action on the well
              "control": usual practice, the well is not surfaced
  assignment  random within strata (field x baseline repeats), 1:1
  outcome     repeat repairs per well over 12 months after enrollment (primary)
  analysis    rate ratio, permutation p-value, bootstrap interval; one look at 12 months
Nothing here produces a savings number from history: that needs follow-up after enrollment.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SYSTEM, CONTROL = "system", "control"


def well_repeat_counts(rep: pd.DataFrame, producing: set[str], end: pd.Timestamp, years_back: int = 0) -> pd.Series:
    """Repeat-within-30-day repair jobs per producing well in one 365-day window
    (`years_back` = 0 is the final 365 days, 1 is the 365 days before that)."""
    r = rep.sort_values(["uwi", "start_date"]).copy()
    r["gap"] = r.groupby("uwi")["start_date"].diff().dt.days
    hi = end - pd.Timedelta(days=365 * years_back)
    win = r[(r["start_date"] > hi - pd.Timedelta(days=365)) & (r["start_date"] <= hi)
            & (r["gap"] > 0) & (r["gap"] <= 30)]
    return win.groupby("uwi").size().reindex(sorted(producing), fill_value=0)


def randomize(df: pd.DataFrame, strata: list[str], seed: int = 0) -> pd.DataFrame:
    """Assign arms 1:1 within each stratum, so arms are balanced to within one well per stratum."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    out["arm"] = CONTROL
    for _, idx in out.groupby(strata, sort=True).groups.items():
        idx = np.array(list(idx))
        rng.shuffle(idx)
        first = SYSTEM if rng.random() < 0.5 else CONTROL  # odd strata: coin flip for the extra well
        other = CONTROL if first == SYSTEM else SYSTEM
        out.loc[idx[0::2], "arm"] = first
        out.loc[idx[1::2], "arm"] = other
    return out


def balance_table(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Baseline means by arm and the standardized mean difference (|SMD| < 0.1 is well balanced)."""
    a, b = df[df["arm"] == SYSTEM], df[df["arm"] == CONTROL]
    rows = []
    for c in cols:
        sd = np.sqrt((a[c].var() + b[c].var()) / 2)
        rows.append({"measure": c, "system": a[c].mean(), "control": b[c].mean(),
                     "smd": float((a[c].mean() - b[c].mean()) / sd) if sd > 0 else 0.0})
    return pd.DataFrame(rows)


def analyze(df: pd.DataFrame, outcome: str, exposure: str | None = None, n_perm: int = 10000,
            n_boot: int = 2000, seed: int = 0) -> dict:
    """Pre-specified read of the pilot: rate ratio (system / control), a permutation p-value
    that makes no distributional assumptions (repeat counts are very lumpy), and a bootstrap
    interval resampling wells within each arm. `exposure` is follow-up years per well."""
    rng = np.random.default_rng(seed)
    y = df[outcome].to_numpy(float)
    e = df[exposure].to_numpy(float) if exposure else np.ones(len(df))
    t = (df["arm"] == SYSTEM).to_numpy()

    def rr(yv, ev, tv):
        num, den = yv[tv].sum() / max(ev[tv].sum(), 1e-12), yv[~tv].sum() / max(ev[~tv].sum(), 1e-12)
        return num / den if den > 0 else np.nan

    observed = rr(y, e, t)
    diff = lambda tv: y[tv].sum() / e[tv].sum() - y[~tv].sum() / e[~tv].sum()
    obs_diff = diff(t)
    perm = np.empty(n_perm)
    for i in range(n_perm):
        perm[i] = diff(rng.permutation(t))
    p = float((np.abs(perm) >= abs(obs_diff) - 1e-12).mean())
    boots = []
    ti, ci = np.where(t)[0], np.where(~t)[0]
    for _ in range(n_boot):
        s, c = rng.choice(ti, len(ti)), rng.choice(ci, len(ci))
        idx = np.concatenate([s, c])
        boots.append(rr(y[idx], e[idx], np.arange(len(idx)) < len(s)))
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    return {"n_system": int(t.sum()), "n_control": int((~t).sum()),
            "rate_system": float(y[t].sum() / e[t].sum()), "rate_control": float(y[~t].sum() / e[~t].sum()),
            "rate_ratio": float(observed), "ci_low": float(lo), "ci_high": float(hi), "p_value": p}


def aa_false_positive_rate(df: pd.DataFrame, outcome: str, strata: list[str], n_trials: int = 200,
                           n_perm: int = 400, seed: int = 0) -> dict:
    """A/A check: randomize the same wells many times with NO intervention and count how often
    the analysis wrongly reports a difference. A trustworthy test gives about 5%."""
    hits = 0
    for i in range(n_trials):
        d = randomize(df, strata, seed=seed + i)
        hits += analyze(d, outcome, n_perm=n_perm, n_boot=50, seed=seed + i)["p_value"] < 0.05
    rate = hits / n_trials
    se = float(np.sqrt(rate * (1 - rate) / n_trials))
    return {"trials": n_trials, "false_positive_rate": rate, "ci_low": max(0.0, rate - 1.96 * se), "ci_high": rate + 1.96 * se}


def power(counts: np.ndarray, n_per_arm: int, effect: float, rng, sims: int = 600, alpha: float = 0.05) -> float:
    """Share of simulated 12-month trials that detect a reduction of `effect` in repeat repairs
    (two-sided Welch test), resampling real wells' counts and thinning the treated arm."""
    from scipy import stats

    hits = 0
    for _ in range(sims):
        control = rng.choice(counts, n_per_arm)
        treated = rng.binomial(rng.choice(counts, n_per_arm), 1 - effect)
        hits += stats.ttest_ind(treated, control, equal_var=False).pvalue < alpha and treated.mean() < control.mean()
    return hits / sims


def minimum_detectable_effect(counts: np.ndarray, n_per_arm: int, rng, target: float = 0.8,
                              grid=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8), sims: int = 400) -> float | None:
    """Smallest reduction in the grid detected with at least `target` power, or None."""
    for e in grid:
        if power(counts, n_per_arm, e, rng, sims) >= target:
            return e
    return None
