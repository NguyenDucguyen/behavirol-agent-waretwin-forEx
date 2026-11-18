# 📐 TỔNG HỢP CÁC THUẬT TOÁN HÀNH VI TÁC TỬ TRONG WARETWIN
## (Multi-Paradigm Agent Behavioral Algorithms in Model-Driven Digital Twin)

> **Tài liệu tham chiếu chuẩn**: [SYSTEM_CONTEXT.md](file:///d:/WareTwin/SYSTEM_CONTEXT.md) · [agent_audit_strategy.md](file:///d:/WareTwin/agent_audit_strategy.md)  
> **Cơ sở hình thức (Formal Metamodels)**: [metamodelBehavirolAg.ecore](file:///d:/WareTwin/model/metamodelBehavirolAg.ecore) · [waretwinExtension.ecore](file:///d:/WareTwin/model/waretwinExtension.ecore) · [wareTwinReasoning.ecore](file:///d:/WareTwin/model/wareTwinReasoning.ecore) · [WareTwinAMR.xmi](file:///d:/WareTwin/model/WareTwinAMR.xmi)

---

## 1. Giới thiệu & Khung Kiến trúc Đa Trường phái Suy luận

Trong hệ thống nhà kho thông minh nhiều tầng **WareTwin**, hành vi của các tác tử không bị "hardcode" thành các câu lệnh `if/else` thủ tục nguyên khối, mà được thiết kế theo phương pháp **Kỹ nghệ Định hướng Mô hình (Model-Driven Engineering - MDE)**. Hệ thống phân định rõ **2 loại tác tử hành vi cốt lõi**:

1. **Loại 1 — Tác tử Xe tự hành (Cargo AMR & Navigation Agent)**:
   * **Bản chất**: Tác tử vật lý phân tán (Distributed Autonomous Physical Agent).
   * **Cấu trúc 3 tầng suy luận**:
     * **Tầng Nhận thức Chiến lược (Strategic Cognition)**: Thuật toán **Hybrid BDI (Belief-Desire-Intention)** định hướng mục tiêu, quản lý kế hoạch và ngắt ưu tiên.
     * **Tầng Phản xạ Chiến thuật & An toàn (Tactical Reactive Safety)**: Thuật toán **Behavior Tree (Cây hành vi 26 Node)** giám sát an toàn LiDAR 100ms, phòng tránh va chạm, giải tỏa bế tắc (Deadlock Recovery).
     * **Tầng Chấp hành Vòng đời & Vật lý (Execution Layer)**: Máy trạng thái hữu hạn (**FSM**) và thuật toán dẫn đường hình học $A^*$ trên lưới 2D kết hợp kiểm tra va chạm OBB SAT.
2. **Loại 2 — Tác tử Điều phối Hạm đội (Fleet Manager Agent)**:
   * **Bản chất**: Tác tử giám sát & phân bổ tài nguyên tập trung (Centralized Supervisory Agent).
   * **Trường phái suy luận**: Thuật toán **Tối ưu hóa Tiện ích Tuyến tính Đa mục tiêu (Adaptive Multi-Objective Linear Utility Optimization)**, đánh giá và giải trình quyết định giao việc (Explainable Decision Rationale) theo thời gian thực.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   HỆ THỐNG ĐA TÁC TỬ WARETWIN                           │
├───────────────────────────────────┬────────────────────────────────────┤
│   LOẠI 1: CARGO AMR ROBOT         │   LOẠI 2: FLEET MANAGER            │
│   (Tác tử Xe tự hành phân tán)    │   (Tác tử Điều phối tập trung)     │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Tầng 1: Hybrid BDI Deliberation │ • Thuật toán Đánh giá Tiện ích     │
│   (Belief ➔ Desire ➔ Intention)   │   Đa mục tiêu (5 yếu tố tuyến tính)│
│ • Tầng 2: Reactive Behavior Tree  │ • Phạt chi phí thang máy mezzanine │
│   (LiDAR Reflex + BackOff Yield)  │ • Thích ứng động trọng số bối cảnh │
│ • Tầng 3: FSM & Kinematics        │ • Audit Trail minh bạch quyết định │
└───────────────────────────────────┴────────────────────────────────────┘
```

---

## 2. Loại Tác tử 1: Cargo AMR & Navigation Agent (Tác tử Xe tự hành)

Mã nguồn triển khai: [bdi_robot.py](file:///d:/WareTwin/backend/app/sim/bdi_robot.py) · [bt_navigator.py](file:///d:/WareTwin/backend/app/sim/bt_navigator.py) · [engine.py](file:///d:/WareTwin/backend/app/sim/engine.py)

### 2.1. Tầng 1: Thuật toán Nhận thức Chiến lược — Hybrid BDI (Belief-Desire-Intention)

Ánh xạ Metamodel: `GOAL_OBJECTIVE`, `PLAN_PROCESS`, `MEANS_END_LINK`, `PREEMPTIVE_INTERRUPT`.

#### A. Mô hình Toán học & Dữ liệu
1. **Tập Niềm tin (Beliefs - $\mathcal{B}$)**:
   $$\mathcal{B} = \langle pos, floor, bat, load, fsm, task, lift\_stage, front\_dist, wait\_ticks, is\_charging \rangle$$
2. **Tập Khát khao / Mục tiêu (Desires - $\mathcal{D}$)**:
   * $\mathcal{D}_{DELIVER}$: Hoàn thành đơn hàng kho $\tau$ với mức ưu tiên $p \in \{\text{CRITICAL, HIGH, NORMAL}\}$.
   * $\mathcal{D}_{RECHARGE}$: Bổ sung năng lượng pin (sạc khẩn cấp khi $bat < 20\%$ hoặc sạc chủ động khi rảnh rỗi).
   * $\mathcal{D}_{PARK}$: Tự động về trạm đỗ bảo toàn không gian hành lang khi $idle\_ticks > 300$.
   * $\mathcal{D}_{STANDBY}$: Trạng thái trực ban sẵn sàng nhận lệnh dispatch.
3. **Tập Ý định / Kế hoạch (Intentions - $\mathcal{I}$)**:
   $$\mathcal{I} = \langle plan\_id, \mathcal{S}, step_{curr}, interruptible, preempted\_reason \rangle$$
   Trong đó $\mathcal{S} = [s_1, s_2, \dots, s_k]$ là chuỗi các bước chấp hành tuần tự.

#### B. Quy tắc Liên kết Phương tiện - Cứu cánh (Means-End Reasoning)
* **Nếu Mục tiêu là $\mathcal{D}_{DELIVER}$**:
  * Kiểm tra vị trí tầng: Nếu $floor(source) \neq floor(dest)$ hoặc $floor(robot) \neq floor(source)$ $\Rightarrow$ Chọn `Plan_CrossFloorTransport` gồm 4 bước: `["TRANSIT_TO_SOURCE", "PICK_CARGO", "TRANSIT_TO_DEST", "DELIVER_CARGO"]`.
  * Nếu cùng tầng $\Rightarrow$ Chọn `Plan_SameFloorTransport` gồm 4 bước: `["MOVE_TO_SOURCE", "PICK_CARGO", "MOVE_TO_DEST", "DELIVER_CARGO"]`.
* **Nếu Mục tiêu là $\mathcal{D}_{RECHARGE}$**:
  * Nếu bị ngắt khẩn cấp do pin yếu $\Rightarrow$ Chọn `Plan_TaskHandoffAndCharge` gồm 3 bước: `["TASK_TRANSFER", "NAVIGATE_TO_CHARGER", "CHARGING"]`.
  * Nếu sạc chủ động $\Rightarrow$ Chọn `Plan_ProactiveCharge` gồm 2 bước: `["NAVIGATE_TO_CHARGER", "CHARGING"]`.

#### C. Cơ chế Ngắt Quyền Ưu tiên (Preemptive Interruption & Safety Invariant)
* **Điều kiện ngắt an toàn (`interruptible`)**:
  $$interruptible = \begin{cases} 
  \text{False}, & \text{nếu } fsm \in \{\text{PICKING, DELIVERING}\} \lor lift\_stage \in \{\text{BOARDING, RIDING, ALIGHTING}\} \\ 
  \text{True}, & \text{ngược lại (đang di chuyển trên hành lang mở)}
  \end{cases}$$
  *Ý nghĩa*: Đảm bảo robot không bao giờ bỏ rơi hàng hóa giữa chừng khi đang nâng hạ hoặc dừng đột ngột bên trong giếng thang máy.
* **Kích hoạt ngắt khi pin nguy cấp**:
  $$\text{Nếu } bat < 20\% \land fsm \in \{\text{NAVIGATING, TRANSPORTING}\} \Rightarrow preempted\_reason = \text{"LOW\_BATTERY"}$$
  Kế hoạch vận chuyển bị ngắt, đơn hàng được hoàn trả lại hàng đợi phân phối (`TASK_TRANSFER`) và robot chuyển sang kế hoạch sạc khẩn cấp.

#### D. Mã giả Thuật toán Chu trình Suy luận BDI (`bdi_deliberate`)
```python
def bdi_deliberate(r, rt, engine):
    # Bước 1: Trích xuất Niềm tin (Beliefs) từ thế giới
    B = extract_beliefs(r, rt, engine)
    
    # Bước 2: Suy luận Mục tiêu cấp cao (Desires)
    if B.fsm in ("LOW_BATTERY", "TASK_TRANSFER") or (B.battery < 20 and B.fsm == "GOING_TO_CHARGE"):
        goal = Goal("RECHARGE_BATTERY", priority=100)
    elif B.has_active_task:
        goal = Goal("DELIVER_CARGO", priority=90 if B.task.priority == "CRITICAL" else 60)
    elif B.idle_ticks > 300:
        goal = Goal("PARK_AT_STATION", priority=30)
    else:
        goal = Goal("STANDBY", priority=10)
        
    # Bước 3: Liên kết Phương tiện - Cứu cánh (Means-End Link)
    if goal.type == "DELIVER_CARGO":
        plan_id = "Plan_CrossFloorTransport" if B.is_cross_floor else "Plan_SameFloorTransport"
        step = map_fsm_to_plan_step(B.fsm, B.load)
        interruptible = not (B.fsm in ("PICKING", "DELIVERING") or B.lift_stage in ("BOARDING", "RIDING", "ALIGHTING"))
        preempted_reason = "LOW_BATTERY" if B.battery < 20 else None
    elif goal.type == "RECHARGE_BATTERY":
        plan_id = "Plan_TaskHandoffAndCharge" if B.is_emergency else "Plan_ProactiveCharge"
        step = map_charging_step(B.fsm)
        interruptible = False if B.is_emergency else (B.fsm != "CHARGING")
        preempted_reason = "LOW_BATTERY" if B.is_emergency else None
    else:
        plan_id = "Plan_IdleStandby"; step = "1/1 WAIT_FOR_DISPATCH"; interruptible = True; preempted_reason = None

    return BdiMentalState(goal.description, plan_id, step, interruptible, preempted_reason)
```

---

### 2.2. Tầng 2: Thuật toán Phản xạ Chiến thuật & An toàn — Behavior Tree (BT)

Ánh xạ Metamodel: `COMPOSITE_GROUP`, `FALLBACK_SELECTOR`, `SEQUENTIAL`, `subUnits`, `AtomicAction`.

Behavior Tree vận hành ở tần số **10 Hz (mỗi chu kỳ 100ms)** như một giám sát viên an toàn phản xạ (Safety Supervisor).

```
NavSafetyRoot (FALLBACK_SELECTOR)
├── Sequence: ExecuteMission (SEQUENTIAL)
│   ├── Condition: has_task?
│   ├── Sequence: SafetyLayer (COMPOSITE_GROUP)
│   │   ├── Selector: LidarResponse (FALLBACK_SELECTOR)
│   │   │   ├── Sequence: ClearPath (SEQUENTIAL)
│   │   │   │   ├── Condition: lidar_clear? (ahead >= 2.0m)
│   │   │   │   └── Action: adjust_speed (v = v_max)
│   │   │   └── Action: emergency_stop (v = 0, STOPPED)
│   │   └── Condition: lidar_ok_or_slowing?
│   └── Selector: Navigate (FALLBACK_SELECTOR)
│       ├── Sequence: NormalNav (SEQUENTIAL)
│       │   ├── Condition: has_path?
│       │   └── Action: follow_path
│       ├── Sequence: NearStationArrive (SEQUENTIAL)
│       │   ├── Condition: near_station? (<= 2 cells)
│       │   └── Action: near_station_arrive
│       ├── Sequence: BackOff (SEQUENTIAL)
│       │   ├── Condition: waited_too_long? (wait_ticks >= 80)
│       │   └── Action: back_off (tìm ô trống tấp lề)
│       ├── Sequence: Replan (SEQUENTIAL)
│       │   ├── Condition: waited_enough? (wait_ticks >= 25)
│       │   └── Action: replan_astar (tìm đường A* mới tránh cản)
│       └── Action: wait_and_replan (giảm tốc, chờ nhường đường)
└── Action: idle
```

#### A. Thuật toán Cảm nhận LiDAR ảo (Virtual LiDAR Reflex)
* Góc quét: $270^\circ$, tầm quét tối đa $R_{max} = 4.0\text{ m}$.
* Khoảng cách cảnh báo giảm tốc: $d < 2.0\text{ m} \Rightarrow$ Trạng thái `SLOWING`, vận tốc tối đa giảm còn $45\%$:
  $$v_{max} = v_{nominal} \cdot 0.45$$
* Khoảng cách phanh khẩn cấp: $d < 0.8\text{ m} \Rightarrow$ Trạng thái `STOPPED`, kích hoạt node lá `emergency_stop`:
  $$v \leftarrow 0, \quad a \leftarrow -2 \cdot a_{max}$$

#### B. Thuật toán Hóa giải Bế tắc (Cooperative Deadlock Resolution & Back-off)
Khi hai robot đối đầu trực diện trong hành lang hẹp:
1. **Kiểm tra Quy tắc Nhường đường (`_yields_to`)**:
   $$\text{Yield}(A, B) = \begin{cases} 
   \text{True}, & \text{nếu } load(A) = 0 \land load(B) > 0 \quad (\text{xe rỗng nhường xe chở hàng}) \\ 
   A_{id} > B_{id}, & \text{nếu } load(A) = load(B) \quad (\text{ưu tiên xe có ID nhỏ hơn})
   \end{cases}$$
2. **Kế hoạch Tấp lề Tạm thời (`act_back_off`)**:
   * Robot phải nhường quét bán kính $3 \times 3$ ô xung quanh để tìm ô trống $c_{safe}$ không nằm trong lộ trình của xe đối diện.
   * Lưu tọa độ đích thực tế vào biến tạm: $resume\_point \leftarrow target$.
   * Đặt cờ $backing\_off \leftarrow \text{True}$ và di chuyển vào ô $c_{safe}$.
3. **Khôi phục Lộ trình Ban đầu (`act_resume`)**:
   * Khi robot đã chạm ô $c_{safe}$, xe kia đã đi qua, robot tự động lấy lại $target \leftarrow resume\_point$ và kích hoạt $A^*$ tái lập lộ trình ban đầu.

---

### 2.3. Tầng 3: Tầng Thực thi & Vòng đời Nhiệm vụ (FSM & Kinematics)

Ánh xạ Metamodel: `REACTIVE_STATE`, `STATE_TRANSITION`, `DomainExtension`.

Máy trạng thái hữu hạn (FSM) quản lý các giai đoạn vật lý của nhiệm vụ kho:

$$\begin{aligned}
\text{IDLE} &\xrightarrow{\text{ev\_task\_assigned}} \text{TASK\_ASSIGNED} \xrightarrow{\text{A* planned}} \text{NAVIGATING} \\
\text{NAVIGATING} &\xrightarrow{\text{arrive\_source}} \text{PICKING} \xrightarrow{\text{dwell countdown}} \text{TRANSPORTING} \\
\text{TRANSPORTING} &\xrightarrow{\text{arrive\_dest}} \text{DELIVERING} \xrightarrow{\text{dwell countdown}} \text{COMPLETED} \rightarrow \text{IDLE}
\end{aligned}$$

* **Chuyển tầng qua Thang máy Mezzanine (Freight Lift 5-Stage Interlock)**:
  $$\text{TO\_LIFT} \rightarrow \text{QUEUED} \rightarrow \text{BOARDING} \rightarrow \text{RIDING} \rightarrow \text{ALIGHTING}$$
  * Đảm bảo nguyên tắc bất biến: Robot chỉ đổi giá trị `floor` khi đã hoàn thành pha `ALIGHTING` và bước ra khỏi cửa thang máy an toàn.

---

## 3. Loại Tác tử 2: Fleet Manager Agent (Tác tử Điều phối Hạm đội)

Mã nguồn triển khai: [engine.py (hàm `_assign_tasks` L330–395)](file:///d:/WareTwin/backend/app/sim/engine.py#L330-L395) · [wareTwinReasoning.ecore](file:///d:/WareTwin/model/wareTwinReasoning.ecore)

### 3.1. Bản chất & Triết lý Hành vi
Fleet Manager là một tác tử **Tối ưu hóa Tiện ích Toàn cục (Utility-Based Agent)**. Thay vì phân việc ngẫu nhiên hoặc chỉ xét khoảng cách ngắn nhất, tác tử này giải bài toán phân bổ công việc bằng cách cực đại hóa hàm tiện ích đa mục tiêu gồm **5 thành phần**: Khoảng cách, Mức pin, Khối lượng công việc đã làm, Tắc nghẽn cung đường và Sức khỏe phần cứng robot.

---

### 3.2. Mô hình Toán học: Hàm Tiện ích Tuyến tính Đa mục tiêu

Với mỗi đơn hàng $\tau$ đang chờ trong hàng đợi và tập các robot rảnh rỗi $\mathcal{R}_{idle} = \{r \mid fsm(r) = \text{IDLE} \land bat(r) \ge 20\%\}$:

Điểm tiện ích tổng hợp $U(r, \tau)$ của robot $r$ đối với tác vụ $\tau$ được tính theo công thức:

$$U(r, \tau) = w_{dist} \cdot f_{dist}(r, \tau) + w_{bat} \cdot f_{bat}(r) + w_{work} \cdot f_{work}(r) + w_{cong} \cdot f_{cong}(r) + w_{hlth} \cdot f_{hlth}(r)$$

Trong đó tổng các trọng số thỏa mãn chuẩn hóa:
$$\sum w_i = w_{dist} + w_{bat} + w_{work} + w_{cong} + w_{hlth} = 0.35 + 0.25 + 0.15 + 0.15 + 0.10 = 1.00$$

#### Chi tiết các hàm thành phần ($f_i \in [0, 1]$):
1. **Hàm Khoảng cách Hiệu dụng ($f_{dist}$)**:
   $$f_{dist}(r, \tau) = 1 - \min\left(1, \frac{d_{eff}(r, \tau)}{120.0}\right)$$
   * Nếu cùng tầng: Khoảng cách hình học Euclid phẳng $d_{eff} = \sqrt{(x_r - x_{src})^2 + (z_r - z_{src})^2}$.
   * **Nếu khác tầng (Cross-Floor Penalty)**: Tính thêm chi phí thang máy và hàng đợi:
     $$d_{eff} = d_{ground} + LIFT\_XFLOOR\_PENALTY\_M + t_{wait} \cdot v_{max} \cdot 0.8$$
     *(Với $LIFT\_XFLOOR\_PENALTY\_M = 40\text{ m}$, $t_{wait}$ là thời gian ước tính thang máy đến đón)*.
2. **Hàm Năng lượng Pin ($f_{bat}$)**:
   $$f_{bat}(r) = \frac{battery(r)}{100.0}$$
3. **Hàm Khối lượng Công việc Công bằng ($f_{work}$)**:
   $$f_{work}(r) = \begin{cases} 
   1.0, & \text{nếu } tasks\_completed \le 4 \quad (\text{LOW}) \\ 
   0.6, & \text{nếu } 5 \le tasks\_completed \le 8 \quad (\text{MEDIUM}) \\ 
   0.2, & \text{nếu } tasks\_completed > 8 \quad (\text{HIGH}) 
   \end{cases}$$
4. **Hàm Tránh Khu vực Tắc nghẽn ($f_{cong}$)**:
   $$f_{cong}(r) = 1.0 - congestion(zone_r)$$
   *(Với $congestion \in [0, 1]$ đo lường mật độ xe di chuyển trong khu vực)*.
5. **Hàm Sức khỏe Robot ($f_{hlth}$)**:
   $$f_{hlth}(r) = \frac{health(r)}{100.0}$$

---

### 3.3. Thuật toán Thích ứng Trọng số Động theo Bối cảnh (Dynamic Context-Aware Adaptation)

Khi điều kiện vận hành kho thay đổi, Fleet Manager tự động điều chỉnh bộ trọng số $\{w_i\}$ để tối ưu hóa KPI:

* **Kịch bản 1 — Giờ Cao điểm Tắc nghẽn Cao ($\max(congestion) > 0.6$)**:
  * Tăng $w_{cong}$ từ $0.15 \rightarrow 0.35$ (+20% Boost).
  * Giảm $w_{dist}$ từ $0.35 \rightarrow 0.20$ và $w_{work}$ từ $0.15 \rightarrow 0.10$.
  * *Tác dụng*: Robot chấp nhận đi đường vòng xa hơn để tránh vùng thắt cổ chai.
* **Kịch bản 2 — Cảnh báo Đội xe Pin Thấp ($> 30\%$ robot có pin $< 35\%$)**:
  * Tăng $w_{bat}$ từ $0.25 \rightarrow 0.40$ (+15% Boost).
  * Giảm $w_{dist}$ từ $0.35 \rightarrow 0.25$.
  * *Tác dụng*: Ưu tiên giữ lại các robot pin yếu đi sạc sớm, giao việc nặng cho xe đầy pin.

---

### 3.4. Cơ chế Giải trình Quyết định (Explainable Decision Audit Trail)

Khác với các hệ thống điều phối "hộp đen", Fleet Manager lưu lại cấu trúc `AiDecision` tại mỗi tick giao việc:
* **Ứng viên trúng tuyển**: Ghi nhận rõ lý do được chọn (ví dụ: `["18m from task", "92% battery", "low workload", "no route congestion"]`).
* **Ứng viên bị từ chối**: Ghi nhận lý do bị loại đối chiếu (ví dụ: `battery too low`, `farther from task`, `high workload`).
* Dữ liệu này được phát trực tiếp qua WebSocket tới `OpsDrawer.tsx` trên Frontend.

#### Mã giả Thuật toán Phân bổ Hạm đội (`_assign_tasks`)
```python
def assign_tasks(state, layout, weights):
    # Sắp xếp đơn hàng chờ theo mức độ ưu tiên: CRITICAL -> HIGH -> NORMAL -> LOW
    waiting_tasks = sort_tasks_by_priority_and_time(state.tasks)
    idle_robots = [r for r in state.robots if r.is_idle and r.battery >= 20]

    for task in waiting_tasks:
        if not idle_robots:
            break
            
        candidates = []
        for r in idle_robots:
            d_eff, lift_id, wait_s = calculate_effective_distance(r, task.source, layout)
            score = (weights.distance   * (1 - min(1, d_eff / 120)) +
                     weights.battery    * (r.battery / 100) +
                     weights.workload   * get_workload_score(r) +
                     weights.congestion * (1 - r.zone_congestion) +
                     weights.health     * (r.health / 100))
            
            reasons = generate_reasons(d_eff, r.battery, r.workload, lift_id, wait_s)
            candidates.append(Candidate(r.id, score, d_eff, reasons))
            
        # Chọn ứng viên có điểm tiện ích cao nhất
        candidates.sort(key=lambda c: -c.score)
        best_candidate = candidates[0]
        
        # Gán lý do bị loại cho các ứng viên còn lại để phục vụ Explainable AI (XAI)
        audit_rejected_reasons(candidates[1:], best_candidate)
        
        # Dispatch
        assign_robot_to_task(best_candidate.robot_id, task.id)
        idle_robots.remove(best_candidate.robot_id)
        record_decision_audit_trail(task.id, best_candidate, candidates)
```

---

## 4. Bản Đồ Ánh Xạ Ngữ Nghĩa Toàn Diện Sang Metamodel `metamodelBehavirolAg.ecore`
### (WareTwin làm Canonical Case Study Mẫu Giữ Nguyên 100% Ngữ Nghĩa Hình Thức)

Hệ thống **WareTwin** được thiết kế để đóng vai trò là một **Mô hình Thể hiện Mẫu (Canonical Model Instance / Case Study)** hoàn chỉnh cho bộ ba Metamodel Ecore:
* **Lõi hành vi (Core)**: [metamodelBehavirolAg.ecore](file:///d:/WareTwin/model/metamodelBehavirolAg.ecore) (Namespace `bcore`)
* **Mở rộng miền kho vận (Domain Extension)**: [waretwinExtension.ecore](file:///d:/WareTwin/model/waretwinExtension.ecore) (Namespace `wext`)
* **Hồ sơ tham số suy luận (Reasoning Profile)**: [wareTwinReasoning.ecore](file:///d:/WareTwin/model/wareTwinReasoning.ecore) (Namespace `wres`)
* **File thể hiện XMI thực tế**: [WareTwinAMR.xmi](file:///d:/WareTwin/model/WareTwinAMR.xmi)

Dưới đây là bảng chú thích và đối chiếu chi tiết từng phần tử hình thức trong Metamodel với các thuật toán và hành vi cụ thể tương ứng trong mã nguồn WareTwin, chứng minh tính **bảo toàn ngữ nghĩa (Semantic Preservation)**:

---

### 4.1. Ánh xạ Đơn vị Hành vi (`BehaviorUnit`) & Vai trò (`BehaviorRole`)

| Khái niệm Metamodel | Giá trị Enum | Ví dụ Cụ thể trong WareTwin | Triển khai Mã nguồn Python | Ngữ nghĩa Hành vi Bảo toàn (Preserved Semantics) |
|---|---|---|---|---|
| **`GOAL_OBJECTIVE`** | `value="0"` | `U_Goal_ExecuteTask` (`Goal_CompleteAssignedWarehouseTask`) | `bdi_robot.py`: `desire = "Complete Task #... (PICK · CRITICAL)"` | **Mục tiêu Nhận thức Tối hậu (BDI Desire)**: Đại diện cho trạng thái mong muốn mà tác tử cam kết đạt được. Có `postCondition`: `taskCompleted == true and hasCargoLoaded == false`. |
| **`PLAN_PROCESS`** | `value="1"` | `U_Plan_SingleFloor` (`Plan_SameFloorTransport`) | `bdi_robot.py`: `intention = "Plan_SameFloorTransport"` | **Quy trình Kế hoạch Nhiều bước (BDI Intention)**: Chuỗi hành động có cấu trúc tuần tự (`SEQUENTIAL`) để hiện thực hóa Goal. Có `preCondition`: `crossFloorRequired == false and batteryPct >= 20`. |
| **`REACTIVE_STATE`** | `value="2"` | `U_State_Idle`, `U_State_Parking`, `U_State_Charging`, `U_State_Offline` | `engine.py`: `r["fsm"] = "IDLE"` / `"CHARGING"` / `"OFFLINE"` | **Trạng thái Phản xạ Tức thời (FSM State)**: Vùng trạng thái vật lý rời rạc mà robot chiếm giữ tại một thời điểm, duy trì bởi `invariantCondition` (ví dụ: `amrState == 'IDLE'`). |
| **`COMPOSITE_GROUP`** | `value="3"` | 1. `U_Composite_ElevatorTransit`<br/>2. BT `NavSafetyRoot`, `SafetyLayer`, `Navigate` | 1. `engine.py` (chu trình 5 pha thang máy)<br/>2. `bt_navigator.py` (`SelectorNode`, `SequenceNode`) | **Tổ hợp Hành vi Phân cấp (Hierarchy Container)**: Khối chứa đệ quy các đơn vị con (`subUnits`), cho phép mô hình hóa cả chu trình phân rã việc (BDI Plan Decomposition) lẫn cây hành vi Behavior Tree. |

---

### 4.2. Ánh xạ Mối Liên kết Nhân quả (`BehaviorLink`) & Bản chất Liên kết (`BehaviorLinkType`)

| Khái niệm Metamodel | Giá trị Enum | Ví dụ Cụ thể trong WareTwin | Triển khai Mã nguồn Python | Ngữ nghĩa Hành vi Bảo toàn (Preserved Semantics) |
|---|---|---|---|---|
| **`STATE_TRANSITION`** | `value="0"` | `Link_Idle30s_To_Park`<br/>`Link_AssignTask_FromIdle`<br/>`Link_TaskDone_ReturnIdle`<br/>`Link_Charged_ResumeIdle` | `engine.py`: `_set_fsm(r, "TASK_ASSIGNED")`<br/>`_set_fsm(r, "IDLE")` | **Chuyển dịch Trạng thái Cổ điển**: Chuyển từ trạng thái $S_1$ sang $S_2$ khi có sự kiện kích hoạt `triggerEvent` (ví dụ `ev_fleet_task_assigned`) và điều kiện bảo vệ `guardCondition` thỏa mãn. |
| **`MEANS_END_LINK`** | `value="1"` | `Link_SingleFloorPlan_To_Goal`<br/>`Link_ElevatorComposite_To_Goal` | `bdi_robot.py`: Lựa chọn kế hoạch `Plan_SameFloorTransport` hoặc `Plan_CrossFloorTransport` gắn với Goal `DELIVER_CARGO` | **Quan hệ Phương tiện - Cứu cánh (BDI Means-End)**: Liên kết một kế hoạch hành động (`PLAN_PROCESS`) như là "phương tiện" trực tiếp để phục vụ "cứu cánh" (`GOAL_OBJECTIVE`). |
| **`TASK_DECOMPOSITION`** | `value="2"` | Phân rã `Composite_MultiFloorElevatorSequence` thành 5 pha: `TO_LIFT` ➔ `QUEUED` ➔ `BOARDING` ➔ `RIDING` ➔ `ALIGHTING` | `engine.py`: `_handle_lift()` chuyển giao trạng thái qua biến `rt.lift_stage` | **Phân rã Tác vụ Thứ bậc**: Chia nhỏ một hành vi phức tạp thành các phân đoạn nhỏ có thể quản lý, kiểm soát và xác thực độc lập. |
| **`PREEMPTIVE_INTERRUPT`** | `value="3"` | `Link_MidTask_LowBatteryHandoff` (Priority 9)<br/>`Link_OfflineFault_Interrupt` (Priority 10) | `engine.py` (L849–854): `_set_fsm(r, "LOW_BATTERY")`<br/>`bdi_robot.py`: `preempted_reason = "LOW_BATTERY"` | **Ngắt Quyền Ưu tiên Cấp cao (Preemption)**: Tác nhân an toàn khẩn cấp cưỡng chế dừng tác vụ hiện tại, giải phóng tài nguyên và kích hoạt kế hoạch xử lý sự cố. |

---

### 4.3. Ánh xạ Toán tử Điều phối (`ExecutionOperator`)

Toán tử này quy định cách thức thực thi các đơn vị con bên trong một `BehaviorUnit` (đặc biệt khi `role = COMPOSITE_GROUP`):

1. **`SINGLE` (`value="0"`)**:
   * *Ngữ nghĩa*: Đơn vị hành vi nguyên tử thực thi độc lập (các node lá trong FSM hoặc ActionNode lá trong BT).
   * *Ví dụ WareTwin*: `emergency_stop`, `follow_path`, `adjust_speed` trong [bt_navigator.py](file:///d:/WareTwin/backend/app/sim/bt_navigator.py).
2. **`SEQUENTIAL` (`value="1"`)**:
   * *Ngữ nghĩa*: Thực thi các phần tử con lần lượt theo thứ tự xác định; bước sau chỉ chạy khi bước trước thành công (`SUCCESS`).
   * *Ví dụ WareTwin*:
     * Trong BDI: `Plan_SameFloorTransport` thực thi lần lượt 6 bước: $A^*$ đến nguồn ➔ Bốc hàng ➔ Cập nhật tải ➔ $A^*$ đến đích ➔ Giao hàng ➔ Đánh dấu xong.
     * Trong Behavior Tree: Các node `SequenceNode` (`ExecuteMission`, `SafetyLayer`, `NormalNav`, `ClearPath`).
3. **`PARALLEL` (`value="2"`)**:
   * *Ngữ nghĩa*: Thực thi đồng thời các nhánh con.
   * *Ví dụ WareTwin*: Trong chu trình tick 100ms, hệ thống chạy song song lớp quan sát an toàn LiDAR (`SafetyLayer`) đồng thời với việc tính toán nội suy động học di chuyển bánh xe (`_move_along_path`).
4. **`FALLBACK_SELECTOR` (`value="3"`)**:
   * *Ngữ nghĩa*: Thử thực thi các nhánh con từ trái sang phải; chỉ cần một nhánh thành công (`SUCCESS` hoặc `RUNNING`) thì dừng; chỉ chuyển sang nhánh sau khi nhánh trước thất bại (`FAILURE`).
   * *Ví dụ WareTwin*:
     * Node gốc `NavSafetyRoot`: Thử `ExecuteMission`, nếu không có việc thì rơi về `idle`.
     * Node `Navigate`: Thử `NormalNav`, nếu vướng cản thử `NearStationArrive`, nếu tắc lâu thử `BackOff` (nhường đường), nếu vẫn tắc thử `Replan` (A* mới), cuối cùng rơi về `wait_and_replan`.
     * Node `LidarResponse`: Thử `ClearPath`, nếu không an toàn rơi về `emergency_stop`.

---

### 4.4. Ánh xạ Hành động Nguyên tử (`AtomicAction`) & Loại Hành động (`ActionType`)

Tất cả các hành động nhỏ nhất của robot đều thuộc lớp `AtomicAction`:

* **`UPDATE_VARIABLE` (`value="0"`)**:
  * *Hành vi trong WareTwin*: Cập nhật biến ngữ cảnh nội bộ.
  * *Ví dụ*: `hasCargoLoaded = true` khi bốc hàng thành công, `amrState = 'TASK_ASSIGNED'` khi nhận lệnh, `battery = battery - drain` sau mỗi tick di chuyển.
* **`EMIT_EVENT` (`value="1"`)**:
  * *Hành vi trong WareTwin*: Phát tín hiệu/sự kiện ra toàn bộ Digital Twin để các hệ thống khác lắng nghe.
  * *Ví dụ*: `engine.emit("OBSTACLE_DETECTED")`, `engine.emit("TASK_STARTED")`, `engine.emit("TASK_TRANSFERRED")`, `engine.emit("LIFT_RESERVATION_RELEASED")`.
* **`INVOKE_BEHAVIOR` (`value="2"`)**:
  * *Hành vi trong WareTwin*: Kích hoạt một khối hành vi hoặc gọi một cây con Behavior Tree.
  * *Ví dụ*: Kích hoạt cây con `LidarResponse` từ node `SafetyLayer`.
* **`SEND_MESSAGE` (`value="3"`)**:
  * *Hành vi trong WareTwin*: Truyền thông điệp giữa các tác tử (Inter-Agent Communication).
  * *Ví dụ*: Robot gửi yêu cầu xếp hàng vào buồng thang máy (`queue["1"].append(robot_id)`), Fleet Manager gửi lệnh phân bổ tác vụ cho robot.
* **`EXECUTE_DOMAIN_TASK` (`value="4"`)**:
  * *Hành vi trong WareTwin*: Điểm nối hình thức trỏ trực tiếp sang các lớp nghiệp vụ mở rộng trong [waretwinExtension.ecore](file:///d:/WareTwin/model/waretwinExtension.ecore):
    * `AStarNavigationTask`: Gọi thuật toán tìm đường trong `astar.py` có xét đến bản đồ tắc nghẽn giao thông (`trafficAware = true`) và phản xạ LiDAR (`lidarCollisionResponse = "DECELERATE_REPLAN_YIELD"`).
    * `CargoHandlingTask`: Thực hiện hành vi dừng chờ bốc/dỡ hàng (`isLoading = true/false`, đếm lùi `PICK_TICKS`/`DROP_TICKS`).
    * `ElevatorTransitTask`: Điều phối tiến trình 5 pha thang máy và kích hoạt tìm lại đường khi thang bị hỏng (`rerouteOnLiftFault = true`).
    * `TaskHandoffAndChargeTask`: Hoàn trả nhiệm vụ về hàng đợi trung tâm (`returnTaskToQueue = true`) và cắm sạc tự động (`connectToCharger = true`).

---

### 4.5. Ánh xạ Biến Ngữ Cảnh (`ContextVariable`) & Sự Kiện Kích Hoạt (`StimulusEvent`)

#### Biến Ngữ Cảnh (`ContextVariable`):
Tương đương với **Beliefs** trong BDI, **State Variables** trong FSM, và **Blackboard Context** trong Behavior Tree:
* `amrState` (String): Trạng thái FSM hiện tại (`IDLE`, `NAVIGATING`, `PICKING`, `TRANSPORTING`, `DELIVERING`, `CHARGING`, `OFFLINE`).
* `batteryPct` (Int): Mức năng lượng pin thực tế ($0 \dots 100\%$).
* `idleTimerSec` (Int): Thời gian rảnh rỗi tích lũy tính bằng giây.
* `hasCargoLoaded` (Boolean): Cờ chỉ báo robot đang mang tải trên lưng.
* `crossFloorRequired` (Boolean): Cờ nhận thức nhiệm vụ có đòi hỏi chuyển tầng qua thang máy.
* `chargerAvailable` (Boolean): Nhận thức về sự tồn tại của trạm sạc trống trong kho.
* `taskCompleted` (Boolean): Cờ ghi nhận hoàn thành chu trình phân phối hàng.

#### Sự Kiện Kích Hoạt (`StimulusEvent`):
* **Sự kiện Nội sinh (`isExternal = false`)**:
  * `ev_idle_timeout_30s`: Phát sinh khi bộ đếm `idleTimerSec >= 30`.
  * `ev_battery_insufficient_for_task`: Phát sinh khi ước tính năng lượng còn lại không đủ hoàn thành nốt đường đi.
  * `ev_battery_recharged_threshold`: Phát sinh khi sạc đạt ngưỡng phục hồi $\ge 80\%$.
* **Sự kiện Ngoại sinh (`isExternal = true`)**:
  * `ev_fleet_task_assigned`: Lệnh giao việc phát ra từ tác tử Fleet Manager.
  * `ev_lidar_obstacle_or_jam`: Tín hiệu từ cảm biến LiDAR phát hiện vật cản $< 2.0\text{ m}$ hoặc tắc đường.
  * `ev_elevator_fault`: Tín hiệu cảnh báo thang máy gặp sự cố kẹt cửa/mất điện từ hệ thống giám sát kho.
  * `ev_robot_set_offline`: Lệnh can thiệp từ người vận hành (User Injection) buộc dừng robot khẩn cấp.

---

### 4.6. Ánh xạ Hồ Sơ Tham Số Suy Luận (`ReasoningProfile`)

Trong Metamodel, `ReasoningProfile` là cơ chế tách biệt thuật toán suy luận và các siêu tham số ra khỏi cấu trúc tĩnh:
1. **`AMRAutonomousReasoningProfile` (áp dụng cho 20 robot AMR)**:
   * Chiến lược suy luận: `selectionStrategy = "HYBRID_BDI_FSM_ASTAR"`.
   * Các tham số ngưỡng bảo toàn ngữ nghĩa:
     * `idleParkTimeoutSec = 30` $\Longleftrightarrow$ `SIM["IDLE_TO_PARK_TICKS"] = 300` (ở tần số $10\text{ Hz}$).
     * `lowBatteryThreshold = 20` $\Longleftrightarrow$ `TH["BATTERY_WARNING"] = 20`.
     * `chargedResumeThreshold = 80` $\Longleftrightarrow$ `TH["BATTERY_CHARGE_TO"] = 95` (ngưỡng sạc đầy).
     * `deadlockYieldWaitSec = 10` $\Longleftrightarrow$ `SIM["WAIT_BACKOFF_TICKS"] = 80` (thời gian chờ trước khi lùi nhường đường).
2. **`FleetManagerScoringProfile` (áp dụng cho Fleet Manager)**:
   * Chiến lược suy luận: `selectionStrategy = "UTILITY"`.
   * Bộ 5 trọng số tiện ích đồng bộ chính xác từng số thập phân:
     * `weightDistance = 0.35`
     * `weightBattery = 0.25`
     * `weightWorkload = 0.15`
     * `weightCongestion = 0.15`
     * `weightRobotHealth = 0.10`
     * `logDecisionRationale = true` (kích hoạt tính giải trình XAI lưu vào `recent_decisions`).

---

### 4.7. Minh Chứng Tính Bảo Toàn Ngữ Nghĩa (Semantic Preservation Guarantee)

Một hệ thống Digital Twin làm ví dụ điển cứu (Example Case Study) được coi là **bảo toàn ngữ nghĩa hoàn hảo** khi thỏa mãn 3 tiêu chuẩn khoa học sau:

1. **Bảo toàn Toán tử Logic (Logical Equivalence)**:
   * Biểu thức kiểm tra trong metamodel:
     ```xml
     <guardCondition expression="batteryPct < 20 and chargerAvailable == true"/>
     ```
   * Hoàn toàn đồng nhất về mặt ngữ nghĩa và kết quả đánh giá với biểu thức logic trong mã Python thực thi:
     ```python
     if r["battery"] < TH["BATTERY_WARNING"] and self._free_charger():
         self._go_charge(r, rt)
     ```
2. **Bảo toàn Thứ bậc Hành vi (Hierarchical Isomorphism)**:
   * Cấu trúc cây Behavior Tree mô hình hóa qua `BehaviorUnit` kiểu `COMPOSITE_GROUP` với các toán tử `FALLBACK_SELECTOR` và `SEQUENTIAL` trong mô hình ánh xạ 1:1 sang cấu trúc cây đối tượng Python (`SelectorNode`, `SequenceNode`) trong [bt_navigator.py](file:///d:/WareTwin/backend/app/sim/bt_navigator.py). Không hề có bước "làm phẳng" (flattening) làm mất tính tổ chức phân cấp.
3. **Bảo toàn Khả năng Quan sát Đa Chiều (Full-Stack Observability)**:
   * Mọi trạng thái nhận thức sinh ra từ mô hình (từ BDI Desire/Intention cho đến Active BT Node) đều được đóng gói nguyên vẹn vào JSON schema phát qua WebSocket lên 3D Digital Twin HUD, bảo toàn tính giải trình (Explainability) từ mô hình hình thức cho đến giao diện hiển thị cuối cùng.

---

## 5. Bảng Tổng Hợp Đối Chiếu 2 Loại Agent

| Tiêu chí | Loại 1: Cargo AMR & Navigation Agent | Loại 2: Fleet Manager Agent |
|---|---|---|
| **Vai trò Hệ thống** | Tác tử Chấp hành Vật lý Phân tán (Distributed Physical Execution) | Tác tử Điều phối Tập trung (Centralized Resource Coordinator) |
| **Trường phái Suy luận** | **Hybrid BDI + Behavior Tree (BT) + FSM** | **Adaptive Multi-Objective Utility Optimization** |
| **Không gian Trạng thái** | Liên tục trong không gian 2D/3D (Tọa độ $x, z$, góc quay $\theta$, vận tốc $v$) | Rời rạc trên hàng đợi nhiệm vụ và tập ứng viên hạm đội |
| **Chu kỳ Đánh giá** | $10\text{ Hz}$ ($100\text{ ms/tick}$) liên tục theo thời gian thực | Kích hoạt theo sự kiện (khi có tác vụ mới hoặc robot hoàn thành việc) |
| **Cơ chế Phản xạ** | Phanh LiDAR tức thời ($< 0.8\text{ m}$), nhường đường khi đối đầu (Yield Back-off) | Tính lại trọng số động khi mật độ kho hoặc mức pin biến động |
| **Cơ chế Khôi phục Lỗi** | $A^*$ Replanning, lùi xe nhường ô bế tắc, đổi thang máy khi có lỗi (`LIFT_FAULT`) | Gán lại việc cho xe khác (`TASK_TRANSFER`), đánh dấu đơn hàng thất bại |
| **Tính Giải trình (XAI)** | Cây nhánh BT (`Active Branch`) & BDI Cognitive State (`Desire/Intention/Step`) | Bảng điểm ứng viên (`Candidate Score`) & Lý do chọn/loại (`Decision Rationale`) |
| **Ánh xạ Ecore Metamodel** | `BehaviorUnit(GOAL_OBJECTIVE, PLAN_PROCESS, COMPOSITE_GROUP)` | `ReasoningProfile(FleetManagerScoringProfile)`, `ContextVariable` |

---

## 6. Giá Trị Đóng Góp Khoa Học (Scientific Contributions)

1. **Giải quyết triệt để vấn đề "Hộp đen" (Explainable Multi-Agent Systems - XMAS)**:
   * Cả 2 loại tác tử đều phơi bày toàn bộ chuỗi suy luận nội tại: Từ mục tiêu chiến lược BDI, phản xạ nhánh cây BT của AMR, cho đến thang điểm tiện ích 5 yếu tố của Fleet Manager.
2. **Phân tách Độc lập các Tầng Nhận thức (Cognitive Decoupling)**:
   * Tầng mục tiêu cấp cao (BDI) hoàn toàn độc lập với thuật toán hình học ($A^*$).
   * Tầng an toàn phản xạ (Behavior Tree) hoạt động như một lớp vỏ bảo vệ độc lập, không làm xáo trộn vòng đời nghiệp vụ (FSM).
3. **Tuân thủ Chuẩn mực Kỹ nghệ Định hướng Mô hình (MDE Formalization)**:
   * Toàn bộ các cấu trúc hành vi đều có thể sinh mã hoặc kiểm chứng hình thức trực tiếp từ các file Metamodel chuẩn Eclipse Modeling Framework (`.ecore` và `.xmi`).

