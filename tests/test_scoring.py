import numpy as np
import pandas as pd

from wellsimple import scoring


def test_expected_loss_scales_with_probability_and_rate():
    p = pd.Series([0.5, 0.5])
    rate = pd.Series([10.0, 30.0])  # second well produces 3x more
    out = scoring.expected_loss(p, rate, typical_cost=5000.0, lost_m3_per_event=20.0,
                                fleet_oil_rate=10.0, netback_per_bbl=50.0)
    # lost oil: 20 m3 and 60 m3 -> times 6.2898 bbl/m3 times $50
    assert np.isclose(out.event_cost[0], 5000 + 20 * 6.2898 * 50)
    assert np.isclose(out.event_cost[1], 5000 + 60 * 6.2898 * 50)
    assert np.isclose(out.expected_loss[0], 0.5 * out.event_cost[0])


def test_expected_loss_handles_missing_rate():
    out = scoring.expected_loss(pd.Series([0.2]), pd.Series([np.nan]), 5000.0, 20.0, 10.0, 50.0)
    assert np.isfinite(out.expected_loss[0])  # falls back to the fleet rate


def test_reasons_only_when_well_is_unusual_in_the_bad_direction():
    ref = pd.DataFrame({
        "pump_efficiency_pct_d": np.linspace(-0.1, 0.1, 100),
        "pcp_pump_rod_torque_ftlb_m30": np.linspace(300, 1000, 100),
    })
    row = pd.Series({"pump_efficiency_pct_d": -0.095, "pcp_pump_rod_torque_ftlb_m30": 400.0})
    out = scoring.reasons_for(row, ref)
    assert out == ["Pump efficiency falling"]  # low torque is not a reason
