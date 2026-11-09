from app.sim.navgrid import load_layout
from app.sim.engine import SimEngine
from app.sim.bt_navigator import bt_tick, describe_tree, Status
from app.schema import TwinState

L = load_layout()


def test_bt_describe_tree():
    """Verify Behavior Tree hierarchy maps to metamodel concepts."""
    info = describe_tree()
    assert info.name == "NavSafetyRoot"
    assert info.node_type == "SELECTOR"
    assert info.metamodel_role == "COMPOSITE_GROUP"
    assert info.metamodel_operator == "FALLBACK_SELECTOR"
    assert len(info.children) == 2

    mission_seq = info.children[0]
    assert mission_seq.name == "ExecuteMission"
    assert mission_seq.node_type == "SEQUENCE"
    assert mission_seq.metamodel_operator == "SEQUENTIAL"


def test_bt_tick_idle_robot():
    """An idle robot without task or path should return SUCCESS with idle leaf node."""
    engine = SimEngine(L, seed=42)
    rid = next(iter(engine.state["robots"]))
    r = engine.state["robots"][rid]
    rt = engine.rt[rid]

    status, active_node, active_branch = bt_tick(r, rt, engine)
    assert status == Status.SUCCESS
    assert active_node == "idle"
    assert active_branch == "Root ➔ Idle"


def test_bt_tick_navigating_robot():
    """A robot with task and path should return RUNNING with follow_path."""
    engine = SimEngine(L, seed=42)
    rid = next(iter(engine.state["robots"]))
    r = engine.state["robots"][rid]
    rt = engine.rt[rid]

    # Assign a dummy path & target
    r["current_task_id"] = "TASK-001"
    rt.target = (10, 10)
    r["path"] = [[5, 5], [5, 6], [10, 10]]
    r["path_index"] = 0

    status, active_node, active_branch = bt_tick(r, rt, engine)
    assert status == Status.RUNNING
    assert active_node == "follow_path"
    assert active_branch == "Navigate ➔ NormalNav"


def test_bt_state_in_engine_step_and_schema_valid():
    """Ensure engine steps properly record bt_status & bt_active_node and validate against TwinState."""
    engine = SimEngine(L, seed=42)
    # Run a few ticks
    for _ in range(50):
        engine.step()

    # Validate schema strictly
    TwinState.model_validate(engine.state)

    # Check that robot dict has the keys
    for r in engine.state["robots"].values():
        assert "bt_status" in r
        assert "bt_active_node" in r
        if r["fsm"] in ("NAVIGATING", "TRANSPORTING", "GOING_TO_CHARGE", "OBSTACLE_DETECTED", "REPLANNING"):
            assert r["bt_status"] in ("RUNNING", "SUCCESS", "FAILURE")
            assert isinstance(r["bt_active_node"], str)
            assert isinstance(r["bt_active_branch"], str)
        else:
            assert r["bt_status"] is None
            assert r["bt_active_node"] is None
            assert r["bt_active_branch"] is None


def test_bt_emergency_stop_on_lidar_obstacle():
    """Verify that when an obstacle is detected in the safety zone, BT triggers emergency stop and halts."""
    engine = SimEngine(L, seed=42)
    rid = next(iter(engine.state["robots"]))
    r = engine.state["robots"][rid]
    rt = engine.rt[rid]

    r["current_task_id"] = "TASK-001"
    rt.target = (10, 10)
    r["path"] = [[5, 5], [5, 6], [10, 10]]
    r["path_index"] = 0
    r["velocity"] = 1.2

    # Simulate dynamic obstacle detected by LiDAR at 1.0m (< PERC_STOP=1.7m)
    rt.front_id = "R02"
    rt.front_dist = 1.0

    status, active_node, active_branch = bt_tick(r, rt, engine, dry_run=False)
    assert active_node == "emergency_stop"
    assert active_branch == "SafetyLayer ➔ LidarResponse"
    assert r["velocity"] == 0
    assert r["perception"]["state"] == "STOPPED"


def test_bt_active_movement_advances_robot():
    """Verify that BT active controller actually moves the robot along the path."""
    engine = SimEngine(L, seed=42)
    rid = next(iter(engine.state["robots"]))
    r = engine.state["robots"][rid]
    rt = engine.rt[rid]

    # Create and assign a real task
    task = engine.create_task("PICK", "HIGH", "SHELF-A01", "PACK-01")
    task["assigned_robot"] = rid
    r["current_task_id"] = task["id"]
    r["fsm"] = "TASK_ASSIGNED"

    initial_pos = list(r["position"])

    # Step engine — FSM transitions to NAVIGATING, BT actively moves the robot
    for _ in range(20):
        engine.step()

    # Robot must have moved from initial position
    assert r["position"] != initial_pos
    assert r["fsm"] == "NAVIGATING"
    assert r["bt_status"] in ("RUNNING", "SUCCESS")
    assert r["bt_active_node"] == "follow_path"
