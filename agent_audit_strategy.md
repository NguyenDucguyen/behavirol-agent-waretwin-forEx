# 🔍 WareTwin Agent Audit & Chiến Lược Triển Khai Toàn Diện (Backend + UI)

> **Mục tiêu**: Nâng cấp hệ thống 4 Agent trong WareTwin theo chuẩn **Model-Driven Engineering (MDE)** và **Explainable Multi-Agent Systems (XMAS)**.
> **Nguyên tắc cốt lõi (Full-Stack Observability)**: Mỗi trường phái suy luận khi được bổ sung vào Backend đều **BẮT BUỘC phải có đại diện trực quan tương ứng trên giao diện người dùng (Frontend 3D HUD & Panels)** để phục vụ bằng chứng thực nghiệm cho bài báo khoa học.

---

## I. Tổng quan kết quả kiểm tra Codebase hiện tại

Kiểm tra đối chiếu giữa **Metamodel Core (`metamodelBehavirolAg.ecore`)** và mã nguồn backend (`app/sim/engine.py`, `app/sim/bt_navigator.py`, `app/ai/vlm.py`, `app/ai/copilot.py`):

| Agent | Trường phái Suy luận | Trạng thái Backend | Trạng thái UI | Mức độ thiếu hụt |
|---|---|---|---|---|
| **1. Cargo AMR Robot** | **Hybrid BDI + FSM** | 🟢 Đã tạo `bdi_robot.py` (Belief-Desire-Intention) | 🟢 Đã hiển thị BDI Mental State & Preemption trên UI | Hoàn thành ✅ |
| **2. Fleet Manager** | **Utility-Based Optimization** | 🟢 Đầy đủ scoring function & decision log | 🟢 Đã có `OpsDrawer` hiển thị score & lý do | Thiếu Dynamic Adaptive Weights & UI Profile |
| **3. Navigation & Safety** | **Behavior Tree (BT)** | 🟢 Đã tạo `bt_navigator.py` (26 nodes) | 🟢 Đã hiển thị Active BT Branch & Leaf Action trên UI | Hoàn thành ✅ |
| **4. Surveillance Camera** | **Reactive FSM / VLM** | 🟡 Có VLM mock/real, nhưng FSM chỉ 2 state | 🟡 Có Live Panel nhưng FSM chỉ hiện ONLINE/OFFLINE | Thiếu Multi-state FSM (`ALERT_MODE`, `TRACKING`) |

---

## II. Chiến lược chi tiết theo từng Agent (Mô hình 3 tầng: Backend ➔ Schema ➔ UI)

```
┌─────────────────────────────────┐
│     Backend Reasoning Logic     │  (bdi_robot.py, bt_navigator.py, vlm.py, engine.py)
└────────────────┬────────────────┘
                 │ serializes into
┌────────────────▼────────────────┐
│   TwinState Contract & Schema   │  (app/schema.py ──WebSocket──> twin_state.ts)
└────────────────┬────────────────┘
                 │ renders onto
┌────────────────▼────────────────┐
│   Frontend UI Observability     │  (SelectedRobotPanel, LiveCameraPanel, OpsDrawer)
└─────────────────────────────────┘
```

---

### Giai đoạn 1 — Navigation & Safety Agent (Behavior Tree) ✅ [HOÀN THÀNH]

**Trường phái**: Behavior Tree (BT)  
**Metamodel Core**: `COMPOSITE_GROUP`, `FALLBACK_SELECTOR`, `SEQUENTIAL`, `subUnits`, `LogicalCondition`

#### 1. Backend & Schema Implementation (Đã hoàn thành)
* **Backend (`app/sim/bt_navigator.py`)**:
  * 26 nodes: `NavSafetyRoot` (`FALLBACK_SELECTOR`) ➔ `ExecuteMission` (`SEQUENTIAL`) ➔ `SafetyLayer` & `Navigate`.
  * Hỗ trợ `dry_run=True` (Shadow mode / Observer) và `dry_run=False` (Active Controller).
  * `bt_tick()` trả về `(Status, active_node_name)`.
  * `SimEngine._step_robot()` gọi `bt_tick()` cho robot đang di chuyển/sạc/tránh cản và ghi nhận `bt_status`, `bt_active_node`.
* **Schema Contract (`app/schema.py` & `frontend/src/schema/twin_state.ts`)**:
  * Đã mở rộng `RobotState`:
    ```python
    bt_status: Optional[Literal["RUNNING", "SUCCESS", "FAILURE"]] = None
    bt_active_node: Optional[str] = None
    ```
* **Unit Testing (`backend/tests/test_bt_navigator.py`)**:
  * 4 tests chuyên biệt đã pass (BT Tree introspection, idle tick, navigating tick, engine step + schema validation).

#### 2. Frontend UI Observability (Đã hoàn thành)
* **Vị trí**: `frontend/src/components/panels/RightPanels.tsx` ➔ `SelectedRobotPanel`.
* Đã tích hợp khối quan sát Behavior Tree: hiển thị chip `RUNNING` / `SUCCESS` / `FAILURE` cùng node đang thực thi `⚡ active_node` live khi người dùng click vào bất kỳ robot nào trên 3D scene.
* Đã kiểm tra build frontend: `npm run build` (tsc + vite) thành công không lỗi.

#### 2. Frontend UI Observability (Hiển thị lên màn hình)
* **Vị trí**: Panel bên phải khi click chọn Robot (`frontend/src/components/panels/RightPanels.tsx` ➔ `SelectedRobotPanel`).
* **UI Mockup**:
  ```
  ┌──────────────────────────────────────────────┐
  │ R04 · F1                              Active │
  │ [Robot 3D Thumb]                             │
  │ Battery: 88% [████████████░░░]               │
  │ State: NAVIGATING · 1.50 m/s · ETA 14s       │
  │ Perception: CLEAR · ahead 4.0 m              │
  ├──────────────────────────────────────────────┤
  │ 🌳 REASONING: BEHAVIOR TREE                  │
  │ Status: [ RUNNING ] (Color: #22d3ee)         │
  │ Active Branch: SafetyLayer ➔ ClearPath       │
  │ Leaf Action: ⚡ follow_path                  │
  │ Fallback Chain: [✓ PathClear] [— Replan]     │
  └──────────────────────────────────────────────┘
  ```
* **Khi có vật cản LiDAR hoặc tắc nghẽn**:
  * Trạng thái đổi sang màu vàng: `[ STOPPED ] Active: LidarResponse ➔ emergency_stop`.
  * Trạng thái đổi sang màu tím: `[ REPLANNING ] Active: Navigate ➔ Replan ➔ replan_astar`.

---

### Giai đoạn 2 — Cargo AMR Robot (Hybrid BDI + FSM) ✅ [HOÀN THÀNH]

**Trường phái**: Hybrid BDI (Belief-Desire-Intention) + Finite State Machine  
**Metamodel Core**: `GOAL_OBJECTIVE`, `PLAN_PROCESS`, `MEANS_END_LINK`, `PREEMPTIVE_INTERRUPT`

#### 1. Backend & Schema Implementation (Đã hoàn thành)
* **Tạo file mới**: `backend/app/sim/bdi_robot.py`
  * `Beliefs`: Nhận thức vị trí, pin, tải trọng, FSM, thông tin nhiệm vụ, tầng lầu, trạng thái thang máy.
  * `Goal` (`GOAL_OBJECTIVE`): `DELIVER_CARGO`, `RECHARGE_BATTERY`, `PARK_AT_STATION`, `STANDBY`.
  * `Intention` (`PLAN_PROCESS`): `Plan_SameFloorTransport`, `Plan_CrossFloorTransport`, `Plan_TaskHandoffAndCharge`, `Plan_ProactiveCharge`, `Plan_ParkStandby`, `Plan_IdleStandby`.
  * `bdi_deliberate(r, rt, engine) -> dict`: Vòng lặp suy luận nhận thức BDI chọn kế hoạch trước khi giao cho FSM thực thi từng bước.
* **Schema Contract (`app/schema.py` & `twin_state.ts`)**:
  * Đã bổ sung `RobotBdiState` và trường `bdi` trong `RobotState`:
    ```python
    class RobotBdiState(_Base):
        desire: Optional[str] = None
        intention: Optional[str] = None
        step: Optional[str] = None
        interruptible: bool = True
        preempted_reason: Optional[str] = None
    ```
* **Unit Testing (`backend/tests/test_bdi_robot.py`)**:
  * 6 tests chuyên biệt đã pass 100% (idle standby, same-floor delivery, cross-floor transport, low-battery preemption, proactive charging, Pydantic strict schema validation).

#### 2. Frontend UI Observability (Đã hoàn thành)
* **Vị trí**: Panel bên phải (`SelectedRobotPanel`) và Hộp thoại chi tiết Robot (`Modals.tsx` ➔ `RobotDetail`).
* **UI Thực tế**:
  * Hiển thị Card `🧠 COGNITIVE BDI` với màu tím nhận thức `#c084fc`.
  * Hiển thị Badge `[ Interruptible ]` (màu xanh lá) hoặc `[ Non-Interruptible ]` (màu vàng khi đang bốc dỡ hàng tại trạm hoặc trong thang máy).
  * Hiển thị mục tiêu Desire: `Complete Task #3812 (PICK · CRITICAL)`.
  * Hiển thị kế hoạch Intention: `Plan_SameFloorTransport` / `Plan_CrossFloorTransport`.
  * Hiển thị bước hiện tại Step: `▶ 2/4 PICK_CARGO`.
* **Khi bị ngắt quyền ưu tiên (`PREEMPTIVE_INTERRUPT`)**:
  * Khi pin < 20%: Badge chuyển màu đỏ cảnh báo: `⚠️ PREEMPT: LOW_BATTERY`.
  * Intention đổi thành: `Plan_TaskHandoffAndCharge` ➔ Tự động bàn giao nhiệm vụ và đi sạc.

---

### Giai đoạn 3 — Surveillance Camera (Reactive FSM & VLM)

**Trường phái**: Reactive FSM / Rule-Based Perception  
**Metamodel Core**: `REACTIVE_STATE`, `StimulusEvent`, `STATE_TRANSITION`, `LogicalCondition`

#### 1. Backend & Schema Implementation
* **Nâng cấp `app/ai/vlm.py`**:
  * Chuyển Camera từ 2 trạng thái (`ONLINE`, `OFFLINE`) thành **4 trạng thái FSM phản xạ**:
    * `ONLINE`: Tuần tra giám sát góc rộng định kỳ.
    * `ALERT_MODE`: Phát hiện bất thường ban đầu (`confidence >= 0.7`).
    * `TRACKING`: Khẳng định mối nguy hại liên tục 2 chu kỳ ➔ Phát lệnh đóng Zone.
    * `OFFLINE`: Sự cố phần cứng/kết nối.
  * Tự động hóa: Background polling task kích hoạt VLM kiểm tra camera mỗi 50 ticks (5s) thay vì chờ user ấn nút.
* **Schema Contract (`app/schema.py` & `twin_state.ts`)**:
  * Mở rộng `CameraState`:
    ```python
    fsm_state: str = "ONLINE"  # "ONLINE" | "ALERT_MODE" | "TRACKING" | "OFFLINE"
    stimulus: Optional[str] = None  # "HUMAN_DETECTED" | "OBSTACLE" | "NONE"
    rule_action: Optional[str] = None  # "BLOCK_ZONE_B" | "CLEAR_ALERT"
    ```

#### 2. Frontend UI Observability (Hiển thị lên màn hình)
* **Vị trí**: `frontend/src/components/panels/RightPanels.tsx` (`LiveCameraPanel`) và 3D Scene Viewport (`Cameras.tsx`).
* **UI Mockup trên Live Camera Panel**:
  ```
  ┌──────────────────────────────────────────────┐
  │ Camera · Zone B         [ ALERT_MODE ⚠️ ]    │
  │ [Live CCTV Canvas Viewport]                  │
  │ Stimulus: HUMAN_DETECTED (Confidence: 89%)   │
  │ Guard Rule: conf >= 0.7 AND blocked == true │
  │ Reactive Action: STATE_TRANSITION ➔ TRACKING │
  │ Effect: Auto-block Zone B (duration 60s)    │
  └──────────────────────────────────────────────┘
  ```
* **Hiệu ứng 3D Viewport**:
  * Vòm nón camera (Frustum wireframe) trong 3D Scene đổi màu trực quan:
    * Xanh lá (`ONLINE`) ➔ Vàng chớp (`ALERT_MODE`) ➔ Đỏ rực (`TRACKING`).

---

### Giai đoạn 4 — Fleet Manager (Adaptive Multi-Objective Utility)

**Trường phái**: Utility-Based Optimization  
**Metamodel Core**: `OBJECTIVE`, `ContextVariable (trọng số)`, `ReasoningProfile (UTILITY)`

#### 1. Backend & Schema Implementation
* **Nâng cấp `app/sim/engine.py` (`_assign_tasks`)**:
  * Hàm tính trọng số thích ứng theo bối cảnh (`_context_weights(tick)`):
    * Giờ cao điểm / Tắc nghẽn cao (`congestion > 0.6`): Tăng trọng số `congestion` từ `0.15 ➔ 0.35` để phân tán lộ trình.
    * Đội xe pin yếu (> 3 robot < 30%): Tăng trọng số `battery` từ `0.25 ➔ 0.40`.
* **Schema Contract (`app/schema.py` & `twin_state.ts`)**:
  * Bổ sung thông tin bối cảnh vào `recent_decisions`:
    ```python
    context_trigger: Optional[str] = None  # "HIGH_CONGESTION_ADAPTATION" | "NOMINAL"
    profile_name: str = "UTILITY_ADAPTIVE"
    ```

#### 2. Frontend UI Observability (Hiển thị lên màn hình)
* **Vị trí**: Bảng điều hành AI Operations (`frontend/src/components/ops/OpsDrawer.tsx`).
* **UI Mockup**:
  ```
  ┌──────────────────────────────────────────────┐
  │ Fleet Manager Decisions                      │
  │ Profile: UTILITY_ADAPTIVE [ Congestion Boost]│
  │ Dynamic Weights:                             │
  │  • Distance:   [████████░░] 30%              │
  │  • Battery:    [██████░░░░] 20%              │
  │  • Congestion: [██████████] 35% (+20% Boost) │
  │  • Workload:   [███░░░░░░░] 10%              │
  │  • Health:     [█░░░░░░░░░] 5%               │
  │ Task #A3812 assigned to R04 (Score: 0.84)   │
  │ Reasons: ✓ lowest congestion route (Zone C)  │
  └──────────────────────────────────────────────┘
  ```

---

## III. Bảng Ma Trận Đóng Góp Khoa Học (Dùng trực tiếp cho Paper)

| Agent Archetype | Mô hình MDE (Ecore) | Triển khai Backend | Quan sát Trực quan Frontend (XAI) | Minh chứng Khoa học (Paper Contribution) |
|---|---|---|---|---|
| **Navigation & Safety** | `BehaviorUnit(role=COMPOSITE_GROUP)` | `bt_navigator.py` (26 nodes BT) | Panel: Active BT Node & Fallback chain | Tách bạch lớp phản xạ an toàn với dẫn đường tối ưu |
| **Cargo AMR Robot** | `BehaviorUnit(role=GOAL_OBJECTIVE)` | `bdi_robot.py` (Belief-Desire-Intention) | Panel: BDI Mental Stack & Preemption Badge | Minh họa khả năng hủy/bàn giao việc khi gặp ngắt ưu tiên |
| **Surveillance Camera** | `BehaviorUnit(role=REACTIVE_STATE)` | `vlm.py` (Multi-state FSM + Polling) | CCTV Panel: Chip FSM State & 3D Frustum color | Tự động hóa chu trình cảm nhận ➔ suy luận ➔ cô lập sự cố |
| **Fleet Manager** | `ReasoningProfile(UTILITY)` | `engine.py` (`_context_weights`) | Ops Drawer: Thanh trọng số thích ứng bối cảnh | Giải thích được quyết định phân việc đa mục tiêu (XAI) |

---

## IV. Danh mục file cần tác động theo quy trình chuẩn

| File | Tầng | Hành động | Mục đích |
|---|---|---|---|
| `backend/app/sim/bt_navigator.py` | Backend | Đã hoàn thành | Khung Behavior Tree và 26 nodes điều phối |
| `backend/app/sim/bdi_robot.py` | Backend | Tạo mới | Mô hình BDI (Belief/Goal/Intention) cho AMR |
| `backend/app/sim/engine.py` | Backend | Cập nhật | Tích hợp BDI Deliberation & Dynamic Weights |
| `backend/app/ai/vlm.py` | Backend | Cập nhật | Thêm Camera 4-state FSM |
| `backend/app/schema.py` | Contract | Cập nhật | Mở rộng TwinState schema cho BT, BDI, Camera FSM |
| `frontend/src/schema/twin_state.ts` | Contract | Cập nhật | Đồng bộ TypeScript interface với Python schema |
| `frontend/src/components/panels/RightPanels.tsx` | Frontend UI | Cập nhật | Thêm block hiển thị BT Node & BDI State cho Robot; FSM State cho Camera |
| `frontend/src/components/ops/OpsDrawer.tsx` | Frontend UI | Cập nhật | Thêm hiển thị Dynamic Weights thích ứng bối cảnh |
| `frontend/src/components/scene/Cameras.tsx` | Frontend UI | Cập nhật | Đổi màu 3D Frustum nón camera theo trạng thái FSM |
