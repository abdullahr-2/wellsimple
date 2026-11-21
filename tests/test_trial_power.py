import importlib.util
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location("trial_power", Path(__file__).resolve().parents[1] / "scripts" / "trial_power.py")
tp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tp)


def test_power_behaves_like_power():
    tp.SIMS = 300
    rng = np.random.default_rng(0)
    counts = np.array([0] * 70 + [1] * 15 + [2] * 8 + [5] * 5 + [12] * 2)  # lumpy, like real repeat counts
    no_effect = tp.power(counts, 150, 0.0, rng)
    assert no_effect < 0.10                       # a null effect is rarely "detected" (about alpha, one-sided half)
    small, big = tp.power(counts, 150, 0.2, rng), tp.power(counts, 150, 0.6, rng)
    assert big > small > no_effect                # bigger effects are easier to detect
    assert tp.power(counts, 600, 0.4, rng) > tp.power(counts, 40, 0.4, rng)  # and more wells help
