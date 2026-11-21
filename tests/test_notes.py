import numpy as np
import pandas as pd

from wellsimple import notes


def _jobs():
    rows = []
    # two clearly different families of notes, repeated so min_df=3 keeps the terms
    for i in range(6):
        rows.append(("a%d" % i, "broken polish rod replaced rod string", 30.0 + i, 4000.0))
        rows.append(("b%d" % i, "pump change new rotor stator installed", 200.0 + i, 20000.0))
    df = pd.DataFrame(rows, columns=["uwi", "text", "life_days", "cost"])
    df["start_date"] = pd.Timestamp("2025-01-01") + pd.to_timedelta(np.arange(len(df)), unit="D")
    df["censored"] = False
    return df


def test_search_returns_same_family_and_outcomes():
    mem = notes.WellMemory(notes.TfidfEncoder(dims=3)).build(_jobs())
    res = mem.search("broken rod string polish", k=4)
    assert all("rod" in p.text for p in res)
    s = notes.summarize(res)
    assert s["median_life_days"] < 50
    assert abs(s["cost_per_day_of_life"] - s["median_cost"] / s["median_life_days"]) < 1e-9


def test_search_respects_time_and_well_exclusions():
    jobs = _jobs()
    mem = notes.WellMemory(notes.TfidfEncoder(dims=3)).build(jobs)
    cutoff = jobs.start_date.iloc[4]
    res = mem.search("pump rotor stator", k=10, before=cutoff)
    assert all(p.start_date < cutoff for p in res)
    res = mem.search("pump rotor stator", k=10, exclude_uwi="b0")
    assert all(p.uwi != "b0" for p in res)
