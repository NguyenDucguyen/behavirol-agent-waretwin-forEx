# 🔍 WareTwin Agent Audit & Chiến Lược Bổ Sung

## Tổng quan kết quả kiểm tra codebase

> Kiểm tra các file: `backend/app/sim/engine.py` (1566 dòng), `backend/app/ai/vlm.py`, `backend/app/ai/copilot.py`, `backend/app/main.py`

---

## 1. Cargo AMR Robot — **ĐÃ CÓ (Một phần)**

**Trường phái**: Hybrid BDI + FSM  
**Metamodel Core cần**: `GOAL_OBJECTIVE`, `PLAN_PROCESS`, `MEANS_END_LINK`, `PREEMPTIVE_INTERRUPT`

### ✅ Đã có trong code

| Thành phần Metamodel | Mapping trong code | File / Dòng |
|---|---|---|
| `PLAN_PROCESS` | FSM states: `NAVIGATING → PICKING → TRANSPORTING → DELIVERING` | `engine.py` L762–881 |
| `MEANS_END_LINK` | `_plan_to()` → A* pathfinding → goal location | `engine.py` L948–1002 |
| `PREEMPTIVE_INTERRUPT` | `OBSTACLE_DETECTED` → `REPLANNING`, `LOW_BATTERY` → `TASK_TRANSFER` | `engine.py` L870–878, L839 |
| BDI Belief | `RobotRt` runtime state (perception, pending, front_id) | `engine.py` L74–91 |
| BDI Desire | `current_task_id`, `destination` | `engine.py` L149–156 |

### ❌ Còn thiếu / Chưa tường minh

| Thành phần Metamodel | Vấn đề | Mức độ |
|---|---|---|
| `GOAL_OBJECTIVE` | Không có class/object tường minh thể hiện "mục tiêu" — goal chỉ ẩn trong `current_task_id` và `phase` string | 🔴 Cao |
| `MEANS_END_LINK` tường minh | Không có cấu trúc data liên kết goal → plan → action có thể truy vết được | 🟡 Trung bình |
| BDI Intention stack | Không có danh sách intentions có thể bị preempt và resume — chỉ có 1 level pending | 🟡 Trung bình |
| Deliberation cycle rõ ràng | Vòng BDI (Perceive → Deliberate → Act) không được phân tách; tất cả gộp trong `_step_robot()` | 🟡 Trung bình |

---

## 2. Fleet Manager — **ĐÃ CÓ (Khá đầy đủ)**

**Trường phái**: Utility-based (tối ưu đa mục tiêu)  
**Metamodel Core cần**: `OBJECTIVE`, `ContextVariable (trọng số)`, `ReasoningProfile (UTILITY)`

### ✅ Đã có trong code

| Thành phần Metamodel | Mapping trong code | File / Dòng |
|---|---|---|
| `OBJECTIVE` (multi) | Task assignment tối ưu theo 5 mục tiêu cùng lúc | `engine.py` L317–381 |
| `ContextVariable (trọng số)` | `weights = {"distance": 0.35, "battery": 0.25, "workload": 0.15, "congestion": 0.15, "health": 0.10}` | `engine.py` L324 |
| `ReasoningProfile (UTILITY)` | Score function kết hợp tuyến tính 5 biến | `engine.py` L353–355 |
| Decision logging | `recent_decisions` với `candidates`, `weights`, `reasons` | `engine.py` L376–380 |
| Copilot rule-based | `rule_based_answer()` tái hiện logic Fleet Manager bằng rule | `copilot.py` L116–134 |

### ❌ Còn thiếu

| Thành phần Metamodel | Vấn đề | Mức độ |
|---|---|---|
| Dynamic weight adaptation | Trọng số cứng coded — không thay đổi theo context (giờ cao điểm, sự cố, v.v.) | 🟡 Trung bình |
| `ReasoningProfile` object | Không có object thể hiện tường minh reasoning profile; chỉ là dict cứng | 🟢 Thấp |
| Multi-objective Pareto front | Chỉ dùng linear scalarization, không có Pareto trade-off analysis | 🟢 Thấp |

---

## 3. Navigation & Safety — **ĐÃ CÓ (Một phần, nhưng thiếu BT)**

**Trường phái**: Behavior Tree (BT)  
**Metamodel Core cần**: `COMPOSITE_GROUP`, `FALLBACK_SELECTOR`, `SEQUENTIAL`, `subUnits`

### ✅ Đã có trong code

| Thành phần | Mapping trong code | File / Dòng |
|---|---|---|
| Sequential navigation | A* path following → cell-by-cell movement | `engine.py` L1004–1119 |
| Fallback cơ bản | `OBSTACLE_DETECTED → REPLANNING → fallback path` | `engine.py` L870–878 |
| Safety stop | LiDAR virtual sensor → `PERC_STOP` → velocity = 0 | `engine.py` L1025–1037 |
| Collision avoidance | OBB overlap + `_back_off()` | `engine.py` L1086–1154 |
| Zone blocking | `blocked_zones` → A* cost penalty | `engine.py` L1249–1261 |

### ❌ Còn thiếu / Thiếu nhiều

| Thành phần Metamodel | Vấn đề | Mức độ |
|---|---|---|
| `COMPOSITE_GROUP` tường minh | Không có cấu trúc BT node — logic phân tán trong `_step_robot()` và `_move_along_path()` | 🔴 Cao |
| `FALLBACK_SELECTOR` | Fallback chain (try A* → try simpler path → back-off → wait) không được cấu trúc như BT node | 🔴 Cao |
| `SEQUENTIAL` node | Sequential behavior nhúng trực tiếp trong Python if/elif, không trace-able | 🟡 Trung bình |
| `subUnits` | Không có khái niệm sub-behavior unit riêng biệt (e.g., "Avoid obstacle" là một BT subtree) | 🟡 Trung bình |
| BT tick/status protocol | Không có `SUCCESS`/`FAILURE`/`RUNNING` trạng thái trả về như BT chuẩn | 🟡 Trung bình |

---

## 4. Surveillance Camera (VLM) — **ĐÃ CÓ (Đủ dùng)**

**Trường phái**: Reactive FSM / Rule-based  
**Metamodel Core cần**: `REACTIVE_STATE`, `StimulusEvent`, `STATE_TRANSITION`, `LogicalCondition`

### ✅ Đã có trong code

| Thành phần Metamodel | Mapping trong code | File / Dòng |
|---|---|---|
| `REACTIVE_STATE` | Camera states: `ONLINE`, `OFFLINE` | `engine.py` L165 |
| `StimulusEvent` | VLM response: `human_detected`, `obstacle`, `spill`, `none` | `vlm.py` L29 |
| `STATE_TRANSITION` | `human_detected + blocked + confidence ≥ 0.7` → `block_zone()` | `main.py` L544–547 |
| `LogicalCondition` | `obs["blocked"] and obs["confidence"] >= 0.7 and event == "human_detected"` | `main.py` L544 |
| Simulated fallback | `simulated_observation()` khi không có LLM key | `vlm.py` L77–83 |
| Real VLM | GPT-4o-mini vision với JSON schema | `vlm.py` L54–74 |

### ❌ Còn thiếu

| Thành phần Metamodel | Vấn đề | Mức độ |
|---|---|---|
| Multi-state FSM | Camera chỉ có 2 trạng thái (ONLINE/OFFLINE); thiếu `ALERT_MODE`, `TRACKING` | 🟡 Trung bình |
| Continuous event stream | VLM chỉ được trigger khi frontend gọi API, không tự chủ polling | 🟡 Trung bình |
| Cross-camera correlation | Không có logic kết hợp quan sát từ nhiều camera | 🟢 Thấp |

---

## 📊 Bảng tổng kết tình trạng Agent

| Agent | Tình trạng | Reasoning Paradigm thực tế trong code | Gap với Metamodel |
|---|---|---|---|
| **Cargo AMR Robot** | 🟡 Một phần | FSM thuần + A\* planning (thiếu BDI deliberation tường minh) | GOAL_OBJECTIVE, Intention stack |
| **Fleet Manager** | 🟢 Đầy đủ nhất | Utility-based scoring đúng paradigm | Weight adaptation dynamic |
| **Navigation & Safety** | 🔴 Thiếu nhiều | Logic phân tán, không có BT structure | Toàn bộ BT node types |
| **Surveillance Camera** | 🟢 Đủ dùng | Reactive FSM đúng paradigm, có LogicalCondition | Multi-state FSM, auto-polling |

---

## 🎯 Chiến Lược Bổ Sung (Theo thứ tự ưu tiên)

### Giai đoạn 1 — Bổ sung Navigation & Safety BT (Ưu tiên cao nhất)

**Lý do**: Đây là agent thiếu cấu trúc nhất, và BT là paradigm được phân biệt rõ nhất với FSM (tránh bị reviewer hỏi "hai cái này khác nhau như thế nào?").

**Tạo file**: `backend/app/sim/bt_navigator.py`

```
Cấu trúc BT đề xuất:
Root (Selector)
├── Sequence: "ExecuteCurrentTask"
│   ├── Condition: has_task?
│   ├── Selector: "Navigate"          ← FALLBACK_SELECTOR
│   │   ├── Sequence: "NormalPath"    ← SEQUENTIAL
│   │   │   ├── Condition: path_clear?
│   │   │   └── Action: follow_path()
│   │   └── Sequence: "ReplanPath"   ← FALLBACK
│   │       ├── Action: replan_astar()
│   │       └── Action: back_off()
│   └── Sequence: "SafetyCheck"      ← COMPOSITE_GROUP
│       ├── Condition: zone_not_blocked?
│       ├── Condition: lidar_clear?
│       └── Action: adjust_speed()
└── Action: idle_behavior()
```

**API tích hợp**: BT.tick() được gọi từ `_step_robot()` như một layer riêng cho quyết định navigation.

---

### Giai đoạn 2 — Tường minh hóa BDI cho Cargo AMR Robot

**Lý do**: Cần phân biệt "Hybrid BDI + FSM" với "FSM thuần" — hiện tại code thiếu Belief-Desire-Intention tường minh.

**Tạo file**: `backend/app/sim/bdi_robot.py`

```python
@dataclass
class Belief:
    position: tuple
    battery: float
    obstacles: list
    zone_status: dict

@dataclass  
class Goal:          # GOAL_OBJECTIVE
    type: str        # "DELIVER", "CHARGE", "PARK"
    target_loc: str
    priority: int
    deadline_tick: int

@dataclass
class Intention:     # Active plan being executed
    goal: Goal
    plan: list[str]  # ["TO_SOURCE", "PICKING", "TO_DEST", "DELIVERING"]
    current_step: int
    interruptible: bool  # PREEMPTIVE_INTERRUPT flag
```

**Tích hợp**: `RobotRt` được mở rộng với `beliefs: Belief`, `desires: list[Goal]`, `intention: Intention`. Hàm `_step_robot()` gọi `bdi_deliberate()` trước khi chạy FSM.

---

### Giai đoạn 3 — Multi-state FSM cho Surveillance Camera

**Lý do**: Tăng số `STATE_TRANSITION` và `REACTIVE_STATE` — quan trọng cho narrative paper.

**Bổ sung vào** `vlm.py`:

```
CameraFSM states:
ONLINE → ALERT_MODE (khi detect human, confidence ≥ 0.7)
ALERT_MODE → TRACKING (khi same zone có event lần 2)
TRACKING → ONLINE (khi zone cleared)
ONLINE → OFFLINE (khi inject CAMERA_OFFLINE)
OFFLINE → ONLINE (khi clear injection)
```

**Thêm auto-polling**: Background task trong `main.py` gọi `vlm_ai.observe()` mỗi N ticks cho mỗi camera ONLINE — không cần frontend trigger.

---

### Giai đoạn 4 — Fleet Manager dynamic weight adaptation (Optional)

**Lý do**: Làm rõ `ContextVariable` biến đổi theo context.

**Bổ sung nhỏ** vào `_assign_tasks()`:

```python
def _context_weights(self, tick: int) -> dict:
    """Dynamic weight theo tình trạng hệ thống — UTILITY paradigm rõ hơn."""
    base = {"distance": 0.35, "battery": 0.25, ...}
    if len([r for r in robots if r["battery"] < 30]) > 3:
        base["battery"] += 0.10  # Fleet pin yếu → ưu tiên battery hơn
    if congestion_index > 0.7:
        base["congestion"] += 0.10  # Tắc nghẽn cao → ưu tiên tránh vùng tắc
    return normalize(base)
```

---

## 📝 Gợi ý cho Paper

### Mapping rõ ràng để đưa vào paper

```
Agent                  | Paradigm      | Code Evidence
-----------------------|---------------|----------------------------------
Cargo AMR Robot        | BDI + FSM     | bdi_robot.py (Goal/Intention) + 
                       |               | engine.py FSM states
Fleet Manager          | Utility-based | engine.py L324 weights dict +
                       |               | L353 score function
Navigation & Safety    | Behavior Tree | bt_navigator.py BT nodes +
                       |               | engine.py pathfinding
Surveillance Camera    | Reactive FSM  | vlm.py observe() + 
                       |               | main.py transition conditions
```

### Điểm mạnh có thể trích dẫn trong paper (đã có trong code)

1. **Fleet Manager**: Decision log `recent_decisions` với `weights` và `reasons` → **explainable AI**
2. **AMR Robot**: `PREEMPTIVE_INTERRUPT` thực sự có trong code (LOW_BATTERY interrupt task)
3. **VLM Camera**: Hybrid real LLM + simulated fallback → **graceful degradation**
4. **Navigation**: Virtual LiDAR perception + physical OBB collision → **layered safety**

---

## 🗂 Files cần tạo mới

| File | Mục đích | Dòng ước tính |
|---|---|---|
| `backend/app/sim/bt_navigator.py` | BT node classes + Navigator BT tree | ~150 dòng |
| `backend/app/sim/bdi_robot.py` | Belief, Goal, Intention dataclasses + deliberation | ~100 dòng |
| `backend/app/sim/agent_registry.py` | Registry mapping agent_id → paradigm metadata (cho paper) | ~50 dòng |

## 🗂 Files cần sửa

| File | Sửa gì |
|---|---|
| `engine.py` | Gọi BT navigator từ `_step_robot()`, gọi BDI deliberation |
| `vlm.py` | Thêm CameraFSM class, multi-state transitions |
| `main.py` | Thêm background task auto-polling VLM |

