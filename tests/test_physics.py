import numpy as np
import pandas as pd

from wellsimple import physics


def _daily(n=80, eff=None, torque=None, rpm=None):
    d = pd.DataFrame({"uwi": "w1", "production_date": pd.date_range("2026-01-01", periods=n)})
    d["pump_efficiency_pct"] = eff if eff is not None else 0.7
    d["pcp_pump_rpm"] = rpm if rpm is not None else 200.0
    d["pcp_pump_rod_torque_ftlb"] = torque if torque is not None else 600.0
    d["pcp_pump_displacement_m3d100rpm"] = 50.0
    d["hours_on_prod"] = 24.0
    return d


NO_REPAIRS = pd.DataFrame({"uwi": pd.Series([], dtype=str), "start_date": pd.to_datetime([])})


def test_efficiency_drop_rate_detects_a_wearing_stator():
    eff = np.linspace(0.8, 0.5, 80)   # losing 0.3 over 79 days
    f = physics.physics_features(_daily(eff=eff), NO_REPAIRS)
    rate = f["eff_drop_rate"].iloc[-1]
    assert np.isclose(rate, -0.3 / 79, rtol=0.05)
    flat = physics.physics_features(_daily(), NO_REPAIRS)["eff_drop_rate"].iloc[-1]
    assert abs(flat) < 1e-9


def test_torque_spike_and_normalisation():
    torque = np.full(80, 600.0); torque[-2] = 1800.0  # a sand slug two days ago
    f = physics.physics_features(_daily(torque=torque), NO_REPAIRS)
    assert np.isclose(f["torque_spike"].iloc[-1], 3.0)
    assert np.isclose(f["torque_per_disp_m30"].iloc[-30], 600.0 / 50.0)


def test_revolutions_and_fatigue_reset_at_each_repair():
    d = _daily(n=10)
    reps = pd.DataFrame({"uwi": ["w1"], "start_date": pd.to_datetime(["2026-01-06"])})
    f = physics.physics_features(d, reps)
    per_day = 200 * 60 * 24 / 1e6
    assert np.isclose(f["revs_since_repair"].iloc[4], 5 * per_day)       # Jan 1-5
    assert np.isclose(f["revs_since_repair"].iloc[5], 1 * per_day)       # reset on the repair day
    rel = (600 / 50) / physics.FLEET_TORQUE_PER_DISP
    assert np.isclose(f["fatigue_since_repair"].iloc[5], per_day * rel ** physics.FATIGUE_EXPONENT, rtol=1e-4)


def test_steady_speed_has_low_variability_and_bad_values_are_ignored():
    rpm = np.full(80, 200.0); rpm[::2] = 260.0
    f = physics.physics_features(_daily(rpm=rpm), NO_REPAIRS)
    assert f["rpm_cv30"].iloc[-1] > 0.1
    bad = physics.physics_features(_daily(eff=np.full(80, 91.0)), NO_REPAIRS)  # placeholder-like values
    assert bad["eff_drop_rate"].isna().all()
