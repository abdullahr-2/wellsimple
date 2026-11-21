import numpy as np
import pandas as pd

from wellsimple import crossmodal


def _dataset(n=240, seed=0):
    """Synthetic failures: a sensor pattern determines which note family and class occur."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        pump = i % 2 == 0
        f = {c: rng.normal(0, 1) for c in crossmodal.MECH_FEATURES}
        f["pump_efficiency_pct_m30"] = (-2.0 if pump else 2.0) + rng.normal(0, .3)
        f["uwi"] = f"w{i}"
        f["field_operating_area"] = "A" if i % 3 else "B"
        f["failure_start_date"] = pd.Timestamp("2025-01-01") + pd.Timedelta(days=i)
        f["failure_class"] = "Pump" if pump else "Rods"
        f["text"] = ("pump change new rotor stator installed worn" if pump
                     else "broken polish rod replaced rod string parted") + f" job{i % 7}"
        rows.append(f)
    return pd.DataFrame(rows)


def test_model_learns_sensor_to_note_mapping():
    ds = _dataset()
    m = crossmodal.CrossModal(dims=5, trees=60).fit(ds.iloc[:200])
    test = ds.iloc[200:].reset_index(drop=True)
    pr = m.proba(test)
    pred = pr.idxmax(axis=1)
    assert (pred == test.failure_class).mean() > 0.9
    got = m.retrieve(test, k=3)
    assert len(got) == len(test)
    hits = [(m.notes_.failure_class.iloc[ix] == test.failure_class.iloc[r]).mean() for r, ix in enumerate(got)]
    assert np.mean(hits) > 0.9


def test_retrieval_exclusions_are_respected():
    ds = _dataset()
    m = crossmodal.CrossModal(dims=5, trees=30).fit(ds.iloc[:200])
    test = ds.iloc[200:210].reset_index(drop=True)
    allowed = test["field_operating_area"].to_numpy(object)[:, None] != m.notes_["field_operating_area"].to_numpy(object)[None, :]
    for r, ix in enumerate(m.retrieve(test, k=5, allowed=allowed)):
        assert all(m.notes_.field_operating_area.iloc[i] != test.field_operating_area.iloc[r] for i in ix)
