"""
Behavior Tree Navigator — Navigation & Safety Agent.

Metamodel Mapping (metamodelBehavirolAg.ecore):
  - BehaviorUnit(role=COMPOSITE_GROUP) → Composite nodes (Sequence, Selector)
  - ExecutionOperator.SEQUENTIAL          → SequenceNode
  - ExecutionOperator.FALLBACK_SELECTOR   → SelectorNode (Fallback)
  - subUnits                              → children list in each composite
  - LogicalCondition                      → ConditionNode.check()
  - AtomicAction(EXECUTE_DOMAIN_TASK)     → ActionNode.execute()
  - ContextVariable                       → Blackboard dict entries

BT protocol: each node.tick(bb) returns SUCCESS / FAILURE / RUNNING.
The tree is ticked once per simulation tick for each robot that is navigating.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

# ── BT tick status ──────────────────────────────────────────────
class Status(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"


# ── Blackboard (= ContextVariable container) ────────────────────
class Blackboard:
    """Shared data context between BT nodes — maps to ContextVariable in the metamodel.

    Each key is a ContextVariable.name, value is the current runtime value.
    Populated before every BT tick from robot dict + RobotRt + SimEngine refs.
    """

    def __init__(self) -> None:
        # Navigation state (set externally before tick)
        self.has_task: bool = False
        self.has_path: bool = False
        self.path_clear: bool = True
        self.zone_blocked: bool = False
        self.lidar_clear: bool = True
        self.lidar_slow: bool = False
        self.front_dist: float = math.inf
        self.remaining_cells: int = 0
        self.near_station: bool = False
        self.mutual_deadlock: bool = False
        self.wait_ticks: int = 0

        # References injected by the engine (not serialised)
        self.robot: Optional[dict[str, Any]] = None
        self.rt: Optional[Any] = None           # RobotRt
        self.engine: Optional[Any] = None       # SimEngine

        # Action outputs (written by leaf nodes)
        self.action_result: Status = Status.SUCCESS
        self.dry_run: bool = True

    # ── convenience ────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        """Serialisable snapshot for logging / decision audit trail."""
        return {
            "has_task": self.has_task,
            "has_path": self.has_path,
            "path_clear": self.path_clear,
            "zone_blocked": self.zone_blocked,
            "lidar_clear": self.lidar_clear,
            "lidar_slow": self.lidar_slow,
            "front_dist": round(self.front_dist, 2),
            "remaining_cells": self.remaining_cells,
            "wait_ticks": self.wait_ticks,
        }


# ── Abstract BT node ────────────────────────────────────────────
class BTNode:
    """Base class for all Behavior Tree nodes.

    Metamodel: BehaviorUnit (id, name, role, subUnits, preCondition…)
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def tick(self, bb: Blackboard) -> Status:
        raise NotImplementedError

    def reset(self) -> None:
        """Reset running state for a fresh tree tick (optional override)."""


# ── Condition node (= LogicalCondition) ──────────────────────────
class ConditionNode(BTNode):
    """Leaf: evaluates a predicate on the Blackboard.

    Maps to BehaviorUnit with preCondition / LogicalCondition.
    Returns SUCCESS if the condition holds, FAILURE otherwise.
    """

    def __init__(self, name: str, predicate: Any) -> None:
        super().__init__(name)
        self._pred = predicate          # Callable[[Blackboard], bool]

    def tick(self, bb: Blackboard) -> Status:
        return Status.SUCCESS if self._pred(bb) else Status.FAILURE


# ── Action node (= AtomicAction / EXECUTE_DOMAIN_TASK) ───────────
class ActionNode(BTNode):
    """Leaf: executes a domain action that may take multiple ticks.

    Returns SUCCESS, FAILURE, or RUNNING.
    """

    def __init__(self, name: str, action: Any) -> None:
        super().__init__(name)
        self._action = action           # Callable[[Blackboard], Status]

    def tick(self, bb: Blackboard) -> Status:
        return self._action(bb)


# ── Composite: SequenceNode (SEQUENTIAL) ─────────────────────────
class SequenceNode(BTNode):
    """COMPOSITE_GROUP with executionOperator = SEQUENTIAL.

    Runs children left-to-right. Returns FAILURE on first child failure,
    RUNNING if a child is running, SUCCESS when all succeed.
    """

    def __init__(self, name: str, children: list[BTNode]) -> None:
        super().__init__(name)
        self.children = children        # subUnits in the metamodel
        self._running_idx = 0

    def tick(self, bb: Blackboard) -> Status:
        for i in range(self._running_idx, len(self.children)):
            status = self.children[i].tick(bb)
            if status == Status.RUNNING:
                self._running_idx = i
                return Status.RUNNING
            if status == Status.FAILURE:
                self._running_idx = 0
                return Status.FAILURE
        self._running_idx = 0
        return Status.SUCCESS

    def reset(self) -> None:
        self._running_idx = 0
        for c in self.children:
            c.reset()


# ── Composite: SelectorNode (FALLBACK_SELECTOR) ─────────────────
class SelectorNode(BTNode):
    """COMPOSITE_GROUP with executionOperator = FALLBACK_SELECTOR.

    Tries children in order. Returns SUCCESS on first child success,
    RUNNING if a child is running, FAILURE when all fail.
    """

    def __init__(self, name: str, children: list[BTNode]) -> None:
        super().__init__(name)
        self.children = children
        self._running_idx = 0

    def tick(self, bb: Blackboard) -> Status:
        for i in range(self._running_idx, len(self.children)):
            status = self.children[i].tick(bb)
            if status == Status.RUNNING:
                self._running_idx = i
                return Status.RUNNING
            if status == Status.SUCCESS:
                self._running_idx = 0
                return Status.SUCCESS
        self._running_idx = 0
        return Status.FAILURE

    def reset(self) -> None:
        self._running_idx = 0
        for c in self.children:
            c.reset()


# ═════════════════════════════════════════════════════════════════
# Domain leaf actions — thin wrappers around existing SimEngine methods
# ═════════════════════════════════════════════════════════════════

def _action_follow_path(bb: Blackboard) -> Status:
    """Walk one tick along the A* path (delegates to engine._move_along_path)."""
    rt = bb.rt
    if rt is None or rt.target is None:
        return Status.SUCCESS               # already arrived
    if bb.dry_run:
        return Status.RUNNING
    eng = bb.engine; r = bb.robot
    eng._move_along_path(r, rt)
    if rt.target is None:
        return Status.SUCCESS
    return Status.RUNNING


def _action_replan_astar(bb: Blackboard) -> Status:
    """Recompute A* path to the same goal, skipping blocked cells."""
    if bb.rt is None or bb.rt.target is None:
        return Status.FAILURE
    if bb.dry_run:
        return Status.SUCCESS
    eng = bb.engine; r = bb.robot; rt = bb.rt
    from .astar import astar, to_cell
    path = astar(
        eng.grids[r["floor"]],
        to_cell(r["position"][0], r["position"][2]),
        rt.target,
        blocked=eng._blocked_cells(r["id"], r["floor"]),
        cost_map=eng._congestion_cost(r["floor"]),
    )
    if path is not None:
        r["path"] = [list(c) for c in path]
        r["path_index"] = 0
        rt.wait_ticks = 0
        eng.emit("ROUTE_REPLANNED", "PLANNER", "LOW",
                 f"{r['id']} BT replan ({len(path)} cells)", robot_id=r["id"],
                 task_id=r["current_task_id"])
        return Status.SUCCESS
    return Status.FAILURE


def _action_back_off(bb: Blackboard) -> Status:
    """Yield: move to a nearby empty cell, then resume."""
    if bb.dry_run:
        return Status.SUCCESS
    eng = bb.engine; r = bb.robot; rt = bb.rt
    eng._back_off(r, rt)
    return Status.SUCCESS if rt.backing_off else Status.FAILURE


def _action_adjust_speed(bb: Blackboard) -> Status:
    """Reduce speed when LiDAR detects a nearby obstacle in SLOW zone."""
    if bb.dry_run:
        return Status.SUCCESS
    r = bb.robot
    if bb.lidar_slow and not bb.lidar_clear:
        r["perception"]["state"] = "SLOWING"
    return Status.SUCCESS


def _action_emergency_stop(bb: Blackboard) -> Status:
    """Full stop: obstacle within PERC_STOP distance."""
    if bb.dry_run:
        return Status.SUCCESS
    r = bb.robot
    r["velocity"] = 0
    r["perception"]["state"] = "STOPPED"
    return Status.SUCCESS


def _action_idle(bb: Blackboard) -> Status:
    """Nothing to do — set velocity 0."""
    if not bb.dry_run and bb.robot:
        bb.robot["velocity"] = 0
    return Status.SUCCESS


def _action_wait_and_replan(bb: Blackboard) -> Status:
    """Wait a bit, then try replanning — delegates to engine FSM transition."""
    if not bb.dry_run and bb.engine and bb.robot:
        bb.engine._set_fsm(bb.robot, "OBSTACLE_DETECTED")
    return Status.SUCCESS


def _action_near_station_arrive(bb: Blackboard) -> Status:
    """Close enough to the station — mark as arrived."""
    if bb.dry_run:
        return Status.SUCCESS
    r = bb.robot; rt = bb.rt
    rt.target = None; r["velocity"] = 0; r["path"] = []; r["path_index"] = 0
    r["eta_s"] = 0; rt.wait_ticks = 0
    return Status.SUCCESS


# ═════════════════════════════════════════════════════════════════
# Build the Navigation & Safety BT tree
# ═════════════════════════════════════════════════════════════════
def build_navigation_bt() -> BTNode:
    """
    Construct the canonical Navigation & Safety BT.

    Tree structure
    ==============
    Root (Selector — FALLBACK_SELECTOR)
    ├─ Sequence: "ExecuteMission"
    │  ├─ Condition: has_task?
    │  ├─ Sequence: "SafetyLayer"              ← COMPOSITE_GROUP
    │  │  ├─ Condition: zone_not_blocked?
    │  │  ├─ Selector: "LidarResponse"         ← FALLBACK_SELECTOR
    │  │  │  ├─ Sequence: "ClearPath"
    │  │  │  │  ├─ Condition: lidar_clear?
    │  │  │  │  └─ Action: adjust_speed
    │  │  │  └─ Action: emergency_stop
    │  │  └─ Condition: lidar_clear_after_check?  (pass-through if SLOWING is ok)
    │  └─ Selector: "Navigate"                 ← FALLBACK_SELECTOR
    │     ├─ Sequence: "NormalNav"              ← SEQUENTIAL
    │     │  ├─ Condition: path_clear?
    │     │  └─ Action: follow_path
    │     ├─ Sequence: "NearStationArrive"
    │     │  ├─ Condition: near_station?
    │     │  └─ Action: near_station_arrive
    │     ├─ Sequence: "Replan"
    │     │  ├─ Condition: waited_enough_to_replan?
    │     │  └─ Action: replan_astar
    │     ├─ Sequence: "BackOff"
    │     │  ├─ Condition: waited_too_long?
    │     │  └─ Action: back_off
    │     └─ Action: wait_and_replan            (last-resort fallback)
    └─ Action: idle
    """

    # ── Conditions ──
    cond_has_task           = ConditionNode("has_task?",           lambda bb: bb.has_task)
    cond_has_path           = ConditionNode("has_path?",           lambda bb: bb.has_path)
    cond_path_clear         = ConditionNode("path_clear?",         lambda bb: bb.path_clear)
    cond_zone_not_blocked   = ConditionNode("zone_not_blocked?",   lambda bb: not bb.zone_blocked)
    cond_lidar_clear        = ConditionNode("lidar_clear?",        lambda bb: bb.lidar_clear)
    cond_lidar_ok           = ConditionNode("lidar_ok_or_slow?",   lambda bb: bb.lidar_clear or bb.lidar_slow)
    cond_near_station       = ConditionNode("near_station?",       lambda bb: bb.near_station)
    cond_wait_replan        = ConditionNode("waited_replan?",      lambda bb: bb.wait_ticks >= 25)
    cond_wait_backoff       = ConditionNode("waited_backoff?",     lambda bb: bb.wait_ticks >= 80)

    # ── Actions ──
    act_follow_path         = ActionNode("follow_path",         _action_follow_path)
    act_replan              = ActionNode("replan_astar",        _action_replan_astar)
    act_back_off            = ActionNode("back_off",            _action_back_off)
    act_adjust_speed        = ActionNode("adjust_speed",        _action_adjust_speed)
    act_emergency_stop      = ActionNode("emergency_stop",      _action_emergency_stop)
    act_idle                = ActionNode("idle",                 _action_idle)
    act_wait_replan         = ActionNode("wait_and_replan",     _action_wait_and_replan)
    act_near_arrive         = ActionNode("near_station_arrive", _action_near_station_arrive)

    # ── Composite tree (bottom-up construction) ──

    # Safety layer: check zone + LiDAR before allowing navigation
    lidar_response = SelectorNode("LidarResponse", [
        SequenceNode("ClearPath", [cond_lidar_clear, act_adjust_speed]),
        act_emergency_stop,
    ])

    safety_layer = SequenceNode("SafetyLayer", [
        cond_zone_not_blocked,
        lidar_response,
        cond_lidar_ok,              # pass-through: if we're SLOWING we can still navigate
    ])

    # Navigation fallback chain
    navigate = SelectorNode("Navigate", [
        SequenceNode("NormalNav",         [cond_path_clear, act_follow_path]),
        SequenceNode("NearStationArrive", [cond_near_station, act_near_arrive]),
        SequenceNode("Replan",            [cond_wait_replan, act_replan]),
        SequenceNode("BackOff",           [cond_wait_backoff, act_back_off]),
        act_wait_replan,                  # last-resort: trigger FSM OBSTACLE_DETECTED
    ])

    # Main mission sequence
    execute_mission = SequenceNode("ExecuteMission", [
        cond_has_task,
        safety_layer,
        navigate,
    ])

    # Root: try mission, else idle
    root = SelectorNode("NavSafetyRoot", [
        execute_mission,
        act_idle,
    ])

    return root


# ═════════════════════════════════════════════════════════════════
# Tree tick orchestrator — called from SimEngine
# ═════════════════════════════════════════════════════════════════
# One shared tree instance per engine (stateless except for running_idx).
# Each robot gets its own Blackboard populated per tick.
_TREE: Optional[BTNode] = None

def _get_tree() -> BTNode:
    global _TREE
    if _TREE is None:
        _TREE = build_navigation_bt()
    return _TREE


def populate_blackboard(bb: Blackboard, r: dict[str, Any], rt: Any, engine: Any) -> None:
    """Fill the Blackboard ContextVariables from the current robot state."""
    from .engine import SIM
    bb.robot = r
    bb.rt = rt
    bb.engine = engine

    bb.has_task = r["current_task_id"] is not None or rt.phase is not None
    bb.has_path = rt.target is not None and r["path_index"] < len(r["path"])

    # Path clearance
    nxt_blocked = False
    if bb.has_path:
        nxt = r["path"][r["path_index"]]
        ncell = (nxt[0], nxt[1])
        from .astar import to_cell
        my_cell = to_cell(r["position"][0], r["position"][2])
        entering = my_cell != ncell
        if entering:
            occ = engine.occupancy.get((r["floor"], ncell[0], ncell[1]))
            if occ and occ != r["id"]:
                nxt_blocked = True
    perc_stop = rt.front_id is not None and rt.front_dist < SIM["PERC_STOP"]
    bb.path_clear = not nxt_blocked and not perc_stop

    # Zone safety
    zone_id = r.get("zone")
    bb.zone_blocked = zone_id in engine.blocked_zones if zone_id else False

    # LiDAR
    bb.lidar_clear = rt.front_id is None or rt.front_dist >= SIM["PERC_STOP"]
    bb.lidar_slow  = rt.front_id is not None and SIM["PERC_STOP"] <= rt.front_dist < SIM["PERC_SLOW"]
    bb.front_dist  = rt.front_dist

    # Navigation progress
    bb.remaining_cells = max(0, len(r["path"]) - r["path_index"])
    bb.near_station = (not rt.backing_off
                       and bb.remaining_cells <= SIM["STATION_ARRIVE_CELLS"]
                       and rt.phase in ("TO_SOURCE", "TO_DEST")
                       and nxt_blocked)
    bb.mutual_deadlock = False       # set by engine if needed
    bb.wait_ticks = rt.wait_ticks


def bt_tick(r: dict[str, Any], rt: Any, engine: Any, dry_run: bool = True) -> Status:
    """Run one BT tick for a robot. Returns the root status."""
    tree = _get_tree()
    tree.reset()
    bb = Blackboard()
    bb.dry_run = dry_run
    populate_blackboard(bb, r, rt, engine)
    status = tree.tick(bb)
    return status


# ═════════════════════════════════════════════════════════════════
# Introspection / Paper support
# ═════════════════════════════════════════════════════════════════
@dataclass
class BTNodeInfo:
    """Serialisable description of a BT node for metamodel paper mapping."""
    name: str
    node_type: str                  # "SEQUENCE" | "SELECTOR" | "CONDITION" | "ACTION"
    metamodel_role: str             # BehaviorRole enum value
    metamodel_operator: str         # ExecutionOperator enum value
    children: list["BTNodeInfo"] = field(default_factory=list)


def describe_tree(node: Optional[BTNode] = None) -> BTNodeInfo:
    """Return a recursive description of the BT for paper / debug purposes."""
    if node is None:
        node = _get_tree()

    if isinstance(node, SequenceNode):
        return BTNodeInfo(
            name=node.name, node_type="SEQUENCE",
            metamodel_role="COMPOSITE_GROUP", metamodel_operator="SEQUENTIAL",
            children=[describe_tree(c) for c in node.children],
        )
    if isinstance(node, SelectorNode):
        return BTNodeInfo(
            name=node.name, node_type="SELECTOR",
            metamodel_role="COMPOSITE_GROUP", metamodel_operator="FALLBACK_SELECTOR",
            children=[describe_tree(c) for c in node.children],
        )
    if isinstance(node, ConditionNode):
        return BTNodeInfo(
            name=node.name, node_type="CONDITION",
            metamodel_role="REACTIVE_STATE", metamodel_operator="SINGLE",
        )
    if isinstance(node, ActionNode):
        return BTNodeInfo(
            name=node.name, node_type="ACTION",
            metamodel_role="PLAN_PROCESS", metamodel_operator="SINGLE",
        )
    return BTNodeInfo(name=node.name, node_type="UNKNOWN",
                      metamodel_role="UNKNOWN", metamodel_operator="UNKNOWN")

