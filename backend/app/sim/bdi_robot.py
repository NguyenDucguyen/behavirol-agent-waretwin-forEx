"""
Cargo AMR Hybrid BDI (Belief-Desire-Intention) Cognitive Architecture
====================================================================
Formalizes the Cargo AMR behavioral reasoning according to metamodelBehavirolAg.ecore:
  - BehaviorUnit(role=GOAL_OBJECTIVE):
      Declarative Desires/Goals (DELIVER_CARGO, RECHARGE_BATTERY, PARK_AT_STATION, STANDBY)
  - BehaviorUnit(role=PLAN_PROCESS):
      Procedural Intentions/Plans (Plan_SameFloorTransport, Plan_CrossFloorTransport,
      Plan_TaskHandoffAndCharge, Plan_ProactiveCharge, Plan_ParkStandby, Plan_IdleStandby)
  - BehaviorLink(linkType=MEANS_END_LINK):
      Deliberation mapping current Beliefs & Desires -> appropriate Intention Plan
  - BehaviorLink(linkType=PREEMPTIVE_INTERRUPT):
      High-priority cognitive interruption (e.g., LOW_BATTERY preemption during delivery,
      triggering task handoff and emergency charging plan)

This module operates in harmony with the Behavior Tree (Reactive Safety & Navigation Supervisor)
and the Low-Level FSM (Execution State Machine).
"""

from __future__ import annotations

import math
from typing import Any, Optional, Literal


# ─────────────────────────────────────────────────────────────
# BDI Data Models
# ─────────────────────────────────────────────────────────────

def _get_loc_floor(engine: Any, loc_id: Optional[str]) -> Optional[int]:
    """Helper to look up floor of a location ID."""
    if not loc_id or not hasattr(engine, "loc"):
        return None
    loc = engine.loc.get(loc_id)
    if not loc:
        return None
    return loc.get("floor", 1)


def bdi_deliberate(
    r: dict[str, Any],
    rt: Any,
    engine: Any,
) -> dict[str, Any]:
    """
    Core BDI Deliberation Cycle for Cargo AMR:
    1. Formulate Beliefs from sensors, physical state, and environment.
    2. Deliberate Desires (Goals) based on mission requirements and operational constraints.
    3. Select Intention (Means-End Plan) to achieve the active Desire.
    4. Evaluate Preemptive Interruptibility and preemption status.

    Returns a dict matching schema.RobotBdiState:
    {
        "desire": str,
        "intention": str,
        "step": str,
        "interruptible": bool,
        "preempted_reason": Optional[str],
    }
    """
    S = engine.state
    fsm = r.get("fsm", "IDLE")
    battery = float(r.get("battery", 100.0))
    current_task_id = r.get("current_task_id")
    task = S.get("tasks", {}).get(current_task_id) if current_task_id else None
    lift_stage = r.get("lift_stage")
    load = r.get("load", {}).get("current", 0)
    phase = getattr(rt, "phase", None)
    idle_ticks = getattr(rt, "idle_ticks", 0)
    last_battery_alert = getattr(rt, "last_battery_alert", "NONE")

    # ─────────────────────────────────────────────────────────
    # 1. Beliefs: Assess environmental and internal state
    # ─────────────────────────────────────────────────────────
    is_offline = (fsm == "OFFLINE")
    is_error = (fsm == "ERROR")
    is_low_battery_emergency = (
        fsm in ("LOW_BATTERY", "TASK_TRANSFER")
        or (fsm == "GOING_TO_CHARGE" and last_battery_alert in ("WARN", "CRIT"))
        or (battery < 20.0 and fsm == "GOING_TO_CHARGE")
    )
    is_active_charging = (fsm == "CHARGING")
    is_proactive_charging = (fsm == "GOING_TO_CHARGE" and not is_low_battery_emergency)
    has_active_mission = bool(task and fsm in ("TASK_ASSIGNED", "NAVIGATING", "PICKING", "TRANSPORTING", "DELIVERING", "OBSTACLE_DETECTED", "REPLANNING"))
    is_parking = (phase == "TO_PARK" or idle_ticks > 300)

    # ─────────────────────────────────────────────────────────
    # 2. Desires (Goals): Hierarchical priority evaluation
    # ─────────────────────────────────────────────────────────
    if is_offline:
        desire = "System Offline (Awaiting Maintenance)"
        goal_type = "STANDBY"
    elif is_error:
        desire = "Error Recovery (Halted)"
        goal_type = "STANDBY"
    elif is_low_battery_emergency:
        desire = "Emergency Recharge (Power Critical)"
        goal_type = "RECHARGE_BATTERY"
    elif is_active_charging:
        desire = f"Recharge Battery ({int(battery)}% ➔ 95%)"
        goal_type = "RECHARGE_BATTERY"
    elif is_proactive_charging:
        desire = "Proactive Battery Replenishment"
        goal_type = "RECHARGE_BATTERY"
    elif has_active_mission:
        prio = task.get("priority", "NORMAL")
        ttype = task.get("type", "TRANSPORT")
        desire = f"Complete Task #{task['id']} ({ttype} · {prio})"
        goal_type = "DELIVER_CARGO"
    elif is_parking:
        desire = "Maintain Depot Readiness (Parked)"
        goal_type = "PARK_AT_STATION"
    else:
        desire = "Standby (Awaiting Fleet Dispatch)"
        goal_type = "STANDBY"

    # ─────────────────────────────────────────────────────────
    # 3. Means-End Reasoning: Select Intention Plan & Step
    # ─────────────────────────────────────────────────────────
    interruptible = True
    preempted_reason: Optional[str] = None

    if goal_type == "DELIVER_CARGO" and task:
        # Determine whether same-floor or cross-floor
        src_floor = _get_loc_floor(engine, task.get("source")) or 1
        dst_floor = _get_loc_floor(engine, task.get("destination")) or 1
        current_floor = r.get("floor", 1)
        cross_floor = (src_floor != dst_floor) or (current_floor != src_floor)

        if cross_floor:
            intention = "Plan_CrossFloorTransport"
            steps = ["TRANSIT_TO_SOURCE", "PICK_CARGO", "TRANSIT_TO_DEST", "DELIVER_CARGO"]
        else:
            intention = "Plan_SameFloorTransport"
            steps = ["MOVE_TO_SOURCE", "PICK_CARGO", "MOVE_TO_DEST", "DELIVER_CARGO"]

        # Track active plan step
        if fsm == "TASK_ASSIGNED":
            step = f"1/4 {steps[0]}"
        elif fsm == "NAVIGATING":
            step = f"1/4 {steps[0]}"
        elif fsm == "PICKING":
            step = f"2/4 {steps[1]}"
            # Non-interruptible while actively executing physical pick dwell
            interruptible = False
        elif fsm == "TRANSPORTING":
            step = f"3/4 {steps[2]}"
        elif fsm == "DELIVERING":
            step = f"4/4 {steps[3]}"
            # Non-interruptible while actively placing cargo
            interruptible = False
        elif fsm == "OBSTACLE_DETECTED" or fsm == "REPLANNING":
            active_step_name = steps[2] if load > 0 else steps[0]
            step = f"⚡ REPLANNING ➔ {active_step_name}"
        else:
            step = f"1/4 {steps[0]}"

        # Lifts are non-interruptible zones (safety invariant)
        if lift_stage in ("BOARDING", "RIDING", "ALIGHTING"):
            interruptible = False

        # Preemptive check: low battery while carrying out delivery
        if battery < 20.0:
            preempted_reason = "LOW_BATTERY"

    elif goal_type == "RECHARGE_BATTERY":
        if is_low_battery_emergency:
            intention = "Plan_TaskHandoffAndCharge"
            preempted_reason = "LOW_BATTERY"
            if fsm in ("LOW_BATTERY", "TASK_TRANSFER"):
                step = "1/3 TASK_TRANSFER"
                interruptible = False
            elif fsm == "GOING_TO_CHARGE":
                step = "2/3 NAVIGATE_TO_CHARGER"
                interruptible = False
            else:
                step = "3/3 CHARGING"
                interruptible = False
        else:
            intention = "Plan_ProactiveCharge"
            if fsm == "GOING_TO_CHARGE":
                step = "1/2 NAVIGATE_TO_CHARGER"
                interruptible = True
            else:
                step = "2/2 CHARGING"
                interruptible = False

    elif goal_type == "PARK_AT_STATION":
        intention = "Plan_ParkStandby"
        if phase == "TO_PARK":
            step = "1/2 MOVE_TO_PARK"
        else:
            step = "2/2 DOCKED_AT_PARK"
        interruptible = True

    else:  # STANDBY / ERROR / OFFLINE
        intention = "Plan_IdleStandby"
        step = "1/1 WAIT_FOR_DISPATCH"
        interruptible = True

    return {
        "desire": desire,
        "intention": intention,
        "step": step,
        "interruptible": interruptible,
        "preempted_reason": preempted_reason,
    }

