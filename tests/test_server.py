import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from wellsimple import notes, server, store as store_mod


def _memory():
    rows = []
    for i in range(6):
        rows.append(("a%d" % i, "broken polish rod replaced rod string", 30.0 + i, 4000.0))
        rows.append(("b%d" % i, "pump change new rotor stator installed", 200.0 + i, 20000.0))
    df = pd.DataFrame(rows, columns=["uwi", "text", "life_days", "cost"])
    df["start_date"] = pd.Timestamp("2025-01-01") + pd.to_timedelta(np.arange(len(df)), unit="D")
    df["censored"] = False
    return notes.WellMemory(notes.TfidfEncoder(dims=3)).build(df)


def _wells():
    return pd.DataFrame({
        "uwi": ["w1", "w2", "w3"],
        "well_name": ["One", "Two", "Three"],
        "field_operating_area": ["F"] * 3,
        "facility_name": ["X"] * 3,
        "surface_latitude": [53.0, 53.5, 54.5],
        "surface_longitude": [-110.0, -110.0, -110.0],
        "p_repair": [0.2, 0.9, 0.5],
        "expected_loss_low": [100.0, 900.0, 500.0],
        "expected_loss_mid": [150.0, 1300.0, 700.0],
        "event_cost_mid": [750.0, 1450.0, 1400.0],
        "reasons": ["", "High rod torque", "Pump efficiency falling"],
        "precedent_life_days": [40.0, np.nan, 90.0],
        "precedent_cost_per_day": [100.0, np.nan, 200.0],
        "last_repair_note": ["broken polish rod", "pump change rotor", ""],
        "last_repair_date": pd.to_datetime(["2026-01-01"] * 3),
        "p_pump": [0.1, 0.6, 0.2], "p_rods": [0.8, 0.3, 0.7], "p_tubing": [0.1, 0.1, 0.1],
        "autopsy_notes": ['[{"text": "broken rotor", "component": "Pump"}]'] * 3,
    })


@pytest.fixture()
def client():
    app = server.create_app(_wells(), {"as_of": "2026-10-27"}, _memory(), store_mod.Store())
    return TestClient(app)


def uwis(r):
    return [w["uwi"] for w in r.json()["wells"]]


def test_priority_modes(client):
    assert uwis(client.get("/api/wells?sort=loss")) == ["w2", "w3", "w1"]
    assert uwis(client.get("/api/wells?sort=risk")) == ["w2", "w3", "w1"]
    client.post("/api/crews/crew-1/location", json={"lat": 53.0, "lon": -110.0})
    assert uwis(client.get("/api/wells?sort=closest&crew_id=crew-1")) == ["w1", "w2", "w3"]
    assert uwis(client.get("/api/wells?sort=furthest&crew_id=crew-1")) == ["w3", "w2", "w1"]
    assert uwis(client.get("/api/wells?min_risk=0.4")) == ["w2", "w3"]


def test_assign_hides_well_and_blocks_double_assignment(client):
    r = client.post("/api/assign", json={"uwi": "w2", "crew_id": "crew-1", "note": "go first"})
    assert r.status_code == 200
    assert "w2" not in uwis(client.get("/api/wells"))
    assert client.post("/api/assign", json={"uwi": "w2", "crew_id": "crew-2"}).status_code == 409
    assert client.post("/api/assign", json={"uwi": "nope", "crew_id": "crew-1"}).status_code == 404
    assert client.post("/api/assign", json={"uwi": "w1", "crew_id": "ghost"}).status_code == 409


def test_resolve_flow_feeds_memory(client):
    aid = client.post("/api/assign", json={"uwi": "w1", "crew_id": "crew-2"}).json()["id"]
    assert [a["uwi"] for a in client.get("/api/assignments?crew_id=crew-2&status=assigned").json()] == ["w1"]
    body = {"work_done": ["Replaced rotor"], "note": "found sand fill at 700 m, bailed", "actual_cost": 8200}
    r = client.post(f"/api/assignments/{aid}/complete", json=body)
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    assert client.post(f"/api/assignments/{aid}/complete", json=body).status_code == 409
    resolved = client.get("/api/assignments?status=resolved").json()
    assert resolved[0]["uwi"] == "w1" and resolved[0]["actual_cost"] == 8200
    assert "w1" not in uwis(client.get("/api/wells?include_assigned=true"))  # resolved wells leave the list
    ov = client.get("/api/overview").json()
    assert ov["resolved_count"] == 1 and ov["open_assignments"] == 0


def test_completed_note_becomes_searchable_precedent(client):
    aid = client.post("/api/assign", json={"uwi": "w3", "crew_id": "crew-1"}).json()["id"]
    client.post(f"/api/assignments/{aid}/complete",
                json={"work_done": [], "note": "polish rod broke at the clamp, replaced polish rod"})
    d = client.get("/api/wells/w1?k=15").json()
    assert any("clamp" in p["text"] for p in d["precedents"])


def test_validation(client):
    aid = client.post("/api/assign", json={"uwi": "w1", "crew_id": "crew-1"}).json()["id"]
    assert client.post(f"/api/assignments/{aid}/complete", json={"work_done": [], "note": ""}).status_code == 422
    assert client.post(f"/api/assignments/{aid}/complete", json={"note": "ok done", "actual_cost": -5}).status_code == 422
    assert client.post("/api/crews/crew-1/location", json={"lat": 999, "lon": 0}).status_code == 422
    assert client.get("/api/wells/unknown").status_code == 404
    assert client.get("/api/wells?sort=bogus").status_code == 422


def test_detail_includes_sensor_based_autopsy(client):
    d = client.get("/api/wells/w2").json()
    assert d["autopsy"]["p"] == {"Pump": 0.6, "Rods": 0.3, "Tubing": 0.1}
    assert d["autopsy"]["notes"][0]["text"] == "broken rotor"
    assert "autopsy_notes" not in d["well"]


def test_pilot_endpoint_and_control_wells_hidden_only_in_pilot_mode():
    plan = {"status": "enrolled, follow-up in progress", "n_system": 1, "n_control": 1}
    pw = pd.DataFrame({"uwi": ["w1", "w2"], "well_name": ["One", "Two"], "field": ["F", "F"],
                       "arm": ["system", "control"], "baseline_repeats": [2, 1]})
    normal = TestClient(server.create_app(_wells(), {}, _memory(), store_mod.Store(), plan, pw))
    assert normal.get("/api/pilot").json()["outcome"] is None          # never invents an effect
    assert "reads out" in normal.get("/api/pilot").json()["outcome_note"]
    assert "w2" in uwis(normal.get("/api/wells"))                       # off by default: nothing hidden
    piloting = TestClient(server.create_app(_wells(), {}, _memory(), store_mod.Store(), plan, pw, hide_control=True))
    assert "w2" not in uwis(piloting.get("/api/wells")) and "w1" in uwis(piloting.get("/api/wells"))
    assert TestClient(server.create_app(_wells(), {}, _memory(), store_mod.Store())).get("/api/pilot").status_code == 404


def test_loss_sort_follows_the_selected_price_scenario():
    w = _wells()
    w.loc[w.uwi == "w1", ["expected_loss_low", "expected_loss_mid"]] = [900.0, 100.0]  # ranks differ by scenario
    c = TestClient(server.create_app(w, {}, _memory(), store_mod.Store()))
    assert uwis(c.get("/api/wells?sort=loss&scenario=low"))[0] == "w1"
    assert uwis(c.get("/api/wells?sort=loss&scenario=mid"))[0] == "w2"
