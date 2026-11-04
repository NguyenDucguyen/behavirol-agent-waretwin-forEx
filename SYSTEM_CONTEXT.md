# WareTwin — System Context & MDE Agent Behavioral Architecture

> **Purpose of this document**: Single Source of Truth (SSoT) for AI agents, developers, and researchers. It provides a compact, high-density system overview, repository index, Model-Driven Engineering (MDE) formalization, and implementation status to minimize token consumption during context loading.

---

## 1. Executive Summary & Scientific Purpose

**WareTwin** is an industrial-grade Digital Twin of an autonomous multi-floor warehouse logistics facility (Mezzanine, 20 AMRs, 2 freight lifts, 3 conveyors, packing/sorting stations, charging pads, CCTV cameras, and IoT sensors).

Beyond operational twin capabilities, WareTwin serves as the experimental testbed for scientific research on **Multi-Paradigm Agent Behavioral Modeling** grounded in **Model-Driven Engineering (MDE)** using Eclipse Modeling Framework (EMF / Ecore).

### The Core Research Problem
Traditional industrial digital twins hardcode agent decision logic directly into procedural code or monolithic Finite State Machines (FSMs). WareTwin proves that complex warehouse agents can be formally modeled using a **Unified Behavioral Metamodel** that spans multiple reasoning paradigms:
1. **Hybrid BDI + FSM** (Goal-directed deliberation with pre-emptive interrupt)
2. **Utility-Based Optimization** (Multi-objective task assignment)
3. **Behavior Tree (BT)** (Hierarchical fallback & reactive safety coordination)
4. **Reactive FSM / Rule-Based** (Event-driven vision perception & hazard isolation)

---

## 2. High-Level Architecture Stack

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                              │
│         Vite 6 + React 19 + TypeScript + Three.js / React Three Fiber     │
│   (3D Digital Twin Canvas, HUD, Lift Animations, CCTV Drawer, Copilot UI) │
└─────────────────────────────────────▲─────────────────────────────────────┘
                                      │ WebSocket (100ms delta patches / full state)
                                      │ REST API (Inject, Tasks, Copilot, VLM)
┌─────────────────────────────────────▼─────────────────────────────────────┐
│                           BACKEND SERVER LAYER                            │
│                 FastAPI + Starlette WebSockets + SQLite                   │
│         app/main.py · app/guard.py (Rate Limit, Caps, Origin Check)       │
└─────────────────────────────────────▲─────────────────────────────────────┘
                                      │ Shared in-memory TwinState JSON
┌─────────────────────────────────────▼─────────────────────────────────────┐
│                       CORE SIMULATION ENGINE LAYER                        │
│                           app/sim/engine.py                               │
│  - Tick loop (100ms / 10Hz)       - Traffic congestion heatmaps           │
│  - Mulberry32 PRNG (deterministic)- A* 2D Grid Pathfinding (astar.py)     │
│  - 2-Floor Mezzanine Lifts FSM    - SAT OBB 2D collision detection        │
│  - Virtual LiDAR (270° / 4m)      - Scenario injection & What-if branching│
└─────────────────────────────────────▲─────────────────────────────────────┘
                                      │ Governs / Reflects
┌─────────────────────────────────────▼─────────────────────────────────────┐
│                  MDE AGENT BEHAVIORAL REASONING LAYER                     │
│  model/*.ecore (EMF Metamodel)  <───>  app/sim/*.py (Agent Controllers)   │
│  - Cargo AMR (Hybrid BDI+FSM)          - bt_navigator.py (Behavior Tree)  │
│  - Fleet Manager (Utility Scoring)     - bdi_robot.py (BDI Core - planned)│
│  - Navigation (Behavior Tree)          - vlm.py (Reactive Perception FSM) │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. MDE Metamodel Specification (`/model`)

The behavioral modeling framework is partitioned into three layered Ecore packages:

### 3.1. Behavioral Core (`model/metamodelBehavirolAg.ecore`) — Namespace: `bcore`
* **`BehavioralCore`**: Root container representing an agent archetype. Holds `contextVariables`, `stimulusEvents`, `behaviorUnits`, `behaviorLinks`, `domainExtensions`, and `reasoningProfile`.
* **`BehaviorUnit`**: Unified behavioral node.
  * **`role` (`BehaviorRole`)**:
    * `GOAL_OBJECTIVE` (0): Declarative goal/desire in BDI.
    * `PLAN_PROCESS` (1): Procedural plan or action chain.
    * `REACTIVE_STATE` (2): Discrete FSM state or condition check.
    * `COMPOSITE_GROUP` (3): Branch/subtree container in Behavior Trees.
  * **`executionOperator` (`ExecutionOperator`)**:
    * `SINGLE` (0): Atomic execution.
    * `SEQUENTIAL` (1): Ordered execution (BT SequenceNode / sequential plans).
    * `PARALLEL` (2): Concurrently executed sub-units.
    * `FALLBACK_SELECTOR` (3): Priority selector (BT SelectorNode).
  * **Conditions**: `preCondition`, `postCondition`, `invariantCondition` (`LogicalCondition` evaluating `ContextVariable`).
  * **Hierarchy**: Recursive `subUnits: BehaviorUnit[*]`.
  * **Actions**: Internal execution of `AtomicAction[*]`.
* **`BehaviorLink`**: Directed transition or causal link between units (`sourceUnit` -> `targetUnit`).
  * **`linkType` (`BehaviorLinkType`)**:
    * `STATE_TRANSITION` (0): Classic FSM transition on event/guard.
    * `MEANS_END_LINK` (1): BDI link associating a Goal with a Plan.
    * `TASK_DECOMPOSITION` (2): Hierarchical task breakdown.
    * `PREEMPTIVE_INTERRUPT` (3): Priority preemption (e.g., low battery abort).
* **`AtomicAction`**: Executable leaf.
  * `actionType`: `UPDATE_VARIABLE`, `EMIT_EVENT`, `INVOKE_BEHAVIOR`, `SEND_MESSAGE`, `EXECUTE_DOMAIN_TASK`.
  * `domainTaskRef`: Pointer to domain extension.

### 3.2. WareTwin Domain Extension (`model/waretwinExtension.ecore`) — Namespace: `wext`
Specializes `DomainExtension` for warehouse logistics tasks:
* `AStarNavigationTask`: Source/dest nodes, traffic awareness, LiDAR response.
* `CargoHandlingTask`: Task type (`PICK`, `REPLENISH`, `TRANSPORT`, `RETURN`), loading flag, rules.py check.
* `ElevatorTransitTask`: Lift phase (`TO_LIFT`, `QUEUED`, `BOARDING`, `RIDING`, `ALIGHTING`), reroute flag.
* `TaskHandoffAndChargeTask`: Task return to queue, charger docking.
* `VLMVisionAnalysisTask`: Hazard detection (`HUMAN_DETECTED`, `OBSTACLE`, `LIQUID_SPILL`), confidence threshold, auto-zone blocking.

### 3.3. Reasoning Profiles (`model/wareTwinReasoning.ecore`) — Namespace: `wres`
Specializes `ReasoningProfile` to parameterize agent decision strategies:
* `AMRAutonomousReasoningProfile`: Idle park timeout (30s), low battery threshold (20%), resume threshold (80%), deadlock wait (10s).
* `FleetManagerScoringProfile`: Multi-objective assignment weights (`weightDistance`: 0.35, `weightBattery`: 0.25, `weightWorkload`: 0.15, `weightCongestion`: 0.15, `weightRobotHealth`: 0.10, log decision rationale: true).

---

## 4. Multi-Paradigm Agent Taxonomy & Implementation Mapping

| Agent Archetype | Reasoning Paradigm | Metamodel Core Elements (`bcore`) | Codebase Location | Implementation State |
|---|---|---|---|---|
| **Cargo AMR Robot** | **Hybrid BDI + FSM** | `GOAL_OBJECTIVE`, `PLAN_PROCESS`, `MEANS_END_LINK`, `PREEMPTIVE_INTERRUPT` | `app/sim/engine.py` (L762–900)<br/>`model/WareTwinAMR.xmi` | 🟡 **Partial**: Full FSM implemented; BDI Desires/Intentions implicit in task phases. Formal `bdi_robot.py` abstraction planned. |
| **Fleet Manager** | **Utility-Based Optimization** | `OBJECTIVE`, `ContextVariable` (weights), `ReasoningProfile` (`UTILITY`) | `app/sim/engine.py` (L317–382)<br/>`app/ai/copilot.py` (L130–135) | 🟢 **Complete**: 5-factor linear utility scoring, explainable candidate audit trail in `recent_decisions`. |
| **Navigation & Safety** | **Behavior Tree (BT)** | `COMPOSITE_GROUP`, `FALLBACK_SELECTOR`, `SEQUENTIAL`, `subUnits` | `app/sim/bt_navigator.py`<br/>`app/sim/engine.py` (L775) | 🟢 **Complete (Shadow Mode)**: 26-node tree, Sequence/Selector composites, Blackboard context, non-breaking observer mode. |
| **Surveillance Camera** | **Reactive FSM / Rule-Based** | `REACTIVE_STATE`, `StimulusEvent`, `STATE_TRANSITION`, `LogicalCondition` | `app/ai/vlm.py`<br/>`app/main.py` (L544–547) | 🟢 **Complete**: GPT-4o-mini vision + fallback simulation, confidence thresholding, dynamic zone blocking. |

---

## 5. Detailed Directory & File Index

```
d:/WareTwin/
├── model/                                  # MDE Meta-models & Model Instances
│   ├── metamodelBehavirolAg.ecore          # Metamodel Core (bcore): BehaviorUnit, Links, Actions
│   ├── waretwinExtension.ecore             # Domain Tasks (wext): AStar, Cargo, Lift, VLM tasks
│   ├── wareTwinReasoning.ecore             # Reasoning Profiles (wres): AMR & Fleet Manager weights
│   └── WareTwinAMR.xmi                     # Canonical XMI instance of 20 AMR Fleet behavior
├── backend/                                # Python FastAPI + Simulation Engine
│   ├── app/
│   │   ├── main.py                         # FastAPI routes, WebSocket /ws broadcast, scenario APIs
│   │   ├── schema.py                       # Pydantic v2 TwinState contract (STRICT SSoT)
│   │   ├── guard.py                        # Security middleware: Rate limiting, origin check, caps
│   │   ├── db.py                           # SQLite async persistence for metrics & replays
│   │   ├── warehouse_layout.json           # Warehouse topology: zones, shelves, lifts, cameras
│   │   ├── sim/                            # Simulation Subsystem
│   │   │   ├── engine.py                   # SimEngine core (1590 lines): tick loop, FSM, lifts, OBB
│   │   │   ├── bt_navigator.py             # Navigation & Safety Behavior Tree (26 nodes)
│   │   │   ├── astar.py                    # 2D Grid A* pathfinder with dynamic blocked/cost masks
│   │   │   ├── navgrid.py                  # Grid loader and multi-floor obstacle rasterizer
│   │   │   ├── whatif.py                   # Branching What-If sandbox (deepcopy state & simulate)
│   │   │   └── rules.py                    # Invariant checks & task type validators
│   │   └── ai/                             # Perception & Advisory AI
│   │       ├── copilot.py                  # AI Operations Copilot (LLM structured output + rules)
│   │       ├── vlm.py                      # Vision-Language hazard observer (OpenAI + mock)
│   │       └── context.py                  # State compressor generating compact LLM prompts
│   └── tests/                              # Comprehensive pytest suite (52 tests)
│       ├── test_engine.py                  # 20-min collision-free run, determinism, deadlock tests
│       ├── test_lifts.py                   # Inter-floor FIFO queue, gates, stalling & resuming
│       ├── test_ai.py                      # Copilot grounded answers, VLM ground truth
│       ├── test_perception.py              # Virtual LiDAR distance and bearing
│       └── test_whatif.py                  # Branching simulation clone and delta KPIs
├── frontend/                               # 3D Digital Twin Client (Vite + React + Three.js)
│   ├── src/
│   │   ├── App.tsx                         # Layout orchestrator, HUD panels, side drawers
│   │   ├── components/                     # 3D Three.js scene & UI widgets
│   │   ├── simulation/                     # TypeScript port of simulation engine (optional client mode)
│   │   ├── schema/                         # TypeScript interfaces mirroring backend schema.py
│   │   └── services/                       # WebSocket client, auto-reconnect, binary/JSON decode
│   └── package.json
└── SYSTEM_CONTEXT.md                       # This document
```

---

## 6. Critical Simulation Invariants & Coding Rules

When modifying or generating backend code, you **MUST** uphold these invariants:

1. **Strict Pydantic Contract (`app/schema.py`)**:
   * All API and WebSocket JSON responses are strictly validated against `TwinState`.
   * **Enum Invariant**: Never emit unregistered string literals. For example, `eng.emit()` `source` **must** be an instance of `EventSource` (`'ROBOT'`, `'SENSOR'`, `'CAMERA'`, `'VLM'`, `'CONVEYOR'`, `'SIMULATION'`, `'FLEET_MANAGER'`, `'PLANNER'`, `'USER'`, `'AI_AGENT'`, `'LIFT'`). Adding arbitrary strings like `'BT_NAV'` will trigger a fatal `ValidationError`.
2. **Determinism & PRNG**:
   * Use `self.rng` (`Mulberry32`) for all simulation random numbers, never Python's `random.random()`. The simulation must be 100% bit-level reproducible across seeds.
3. **Tick Cadence & Time Units**:
   * Fundamental simulation tick: `TICK_S = 0.1` (100 ms per tick).
   * 1 second = 10 ticks. 1 minute = 600 ticks.
   * `velocity` is in m/s, acceleration is applied per `SIM["TICK_S"]`.
4. **Physical Coordinates**:
   * Grid cells are $1.0\,\text{m} \times 1.0\,\text{m}$.
   * Robot dimensions: length 0.95 m, width 0.68 m (half-length: 0.475, half-width: 0.34).
   * Floor 1 elevation: $y = 0.0\,\text{m}$. Floor 2 elevation: $y = 6.0\,\text{m}$.
   * Multi-floor transitions occur **only** via freight lifts through strict micro-stepping (`ALIGHTING` phase). Robots never teleport between floors.
5. **Separation of Shadow Mode vs Active Control**:
   * Experimental agent controllers (like `bt_navigator.py`) run in **Shadow Mode** (`dry_run=True`) by default.
   * A shadow controller evaluates state and records its reasoning, but **must never mutate the robot's physical position (`_move_along_path`) or emit duplicate motion commands** in the same tick as `engine.py`'s native FSM.

---

## 7. Current Project Status & Next Steps

### Current Status
* Core warehouse simulation is fully operational with 20 AMRs, 2 lifts, dynamic traffic, LiDAR obstacle avoidance, and What-if branching.
* Phase 1 of Agent MDE formalization is complete: Behavior Tree Navigator (`bt_navigator.py`) is integrated into `SimEngine` in shadow mode, with 100% passing tests.

### Roadmap for Scientific Validation
1. **Cargo AMR BDI Deliberation Layer (`bdi_robot.py`)**:
   * Formalize explicit `Goal` and `Intention` stacks on AMR to represent `GOAL_OBJECTIVE` and `MEANS_END_LINK` before delegating steps to the low-level FSM.
2. **Surveillance Camera Multi-State FSM**:
   * Elevate CCTV cameras from binary `ONLINE`/`OFFLINE` to `ONLINE` -> `ALERT_MODE` -> `TRACKING` -> `ONLINE`.
3. **Frontend Observability HUD**:
   * Expose `bt_status` and active reasoning profile in the React AMR inspection panel so reviewers can see agent reasoning paradigms live in the 3D viewport.

