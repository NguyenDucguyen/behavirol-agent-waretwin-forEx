"""
Unit tests for Cargo AMR Hybrid BDI (Belief-Desire-Intention) Cognitive Architecture
"""
import pytest
from app.sim.engine import SimEngine
from app.sim.navgrid import load_layout
from app.sim.bdi_robot import bdi_deliberate
from app.schema import TwinState

L = load_layout()


def test_bdi_idle_robot():
    """Verify that an idle robot deliberates to Standby goal and Idle intention."""
    e = SimEngine(L, seed=42)
    e.step()
    r = e.state["robots"]["R01"]
    bdi = r.get("bdi")
    assert bdi is not None
    assert "Standby" in bdi["desire"]
    assert bdi["intention"] == "Plan_IdleStandby"
    assert "WAIT_FOR_DISPATCH" in bdi["step"]
    assert bdi["interruptible"] is True
    assert bdi["preempted_reason"] is None


def test_bdi_task_assigned_and_picking():
    """Verify deliberation across mission phases (same-floor vs cross-floor, picking non-interruptible)."""
    e = SimEngine(L, seed=7)
    # Same floor task: SHELF-A01 (F1) -> PACK-01 (F1)
    t = e.create_task("PICK", "CRITICAL", "SHELF-A01", "PACK-01")
    # Step until task is assigned and in progress
    for _ in range(50):
        e.step()
        if t["assigned_robot"]:
            break
    rid = t["assigned_robot"]
    assert rid is not None
    r = e.state["robots"][rid]
    bdi = r.get("bdi")
    assert bdi is not None
    assert f"Task #{t['id']}" in bdi["desire"]
    assert bdi["intention"] == "Plan_SameFloorTransport"
    assert bdi["interruptible"] is True

    # Step until robot reaches PICKING state
    for _ in range(500):
        e.step()
        if r["fsm"] == "PICKING":
            break
    if r["fsm"] == "PICKING":
        bdi = r["bdi"]
        assert "PICK_CARGO" in bdi["step"]
        # Non-interruptible during physical cargo dwell
        assert bdi["interruptible"] is False


def test_bdi_cross_floor_transport():
    """Verify deliberation selects Plan_CrossFloorTransport when task involves mezzanine."""
    e = SimEngine(L, seed=7)
    # Cross floor task: SHELF-M05 (F2) -> PACK-01 (F1)
    t = e.create_task("PICK", "HIGH", "SHELF-M05", "PACK-01")
    for _ in range(50):
        e.step()
        if t["assigned_robot"]:
            break
    rid = t["assigned_robot"]
    assert rid is not None
    r = e.state["robots"][rid]
    bdi = r.get("bdi")
    assert bdi is not None
    assert bdi["intention"] == "Plan_CrossFloorTransport"


def test_bdi_low_battery_preemption():
    """Verify PREEMPTIVE_INTERRUPT triggers emergency charge plan with reason LOW_BATTERY."""
    e = SimEngine(L, seed=9)
    r = e.state["robots"]["R02"]
    rt = e.rt["R02"]
    # Force low battery state during mission
    t = e.create_task("PICK", "NORMAL", "SHELF-M01", "PACK-01")
    for _ in range(20):
        e.step()
    r["fsm"] = "LOW_BATTERY"
    r["battery"] = 12.0
    bdi = bdi_deliberate(r, rt, e)
    assert "Emergency Recharge" in bdi["desire"]
    assert bdi["intention"] == "Plan_TaskHandoffAndCharge"
    assert bdi["preempted_reason"] == "LOW_BATTERY"
    assert bdi["interruptible"] is False


def test_bdi_proactive_charging():
    """Verify proactive charging intention when robot battery is low but not emergency."""
    e = SimEngine(L, seed=15)
    r = e.state["robots"]["R03"]
    rt = e.rt["R03"]
    r["fsm"] = "GOING_TO_CHARGE"
    r["battery"] = 30.0
    rt.last_battery_alert = "NONE"
    bdi = bdi_deliberate(r, rt, e)
    assert bdi["intention"] == "Plan_ProactiveCharge"
    assert bdi["preempted_reason"] is None


def test_bdi_schema_validation():
    """Ensure engine state with BDI mental states strictly validates against Pydantic TwinState schema."""
    e = SimEngine(L, seed=23)
    e.create_task("PICK", "HIGH", "SHELF-M10", "PACK-02")
    for _ in range(30):
        e.step()
    # Pydantic schema validation (extra='forbid')
    twin = TwinState.model_validate(e.state)
    for rid, rob in twin.robots.items():
        assert rob.bdi is not None
        assert rob.bdi.desire is not None
        assert rob.bdi.intention is not None
        assert rob.bdi.step is not None
