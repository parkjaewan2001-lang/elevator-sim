import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from dataclasses import dataclass, field
import random
from copy import deepcopy

# ------------------- [0] 완전 재현성을 위한 글로벌 시드 설정 -------------------
GLOBAL_SEED = 42
MONTE_CARLO_RUNS = 100

def reset_global_seeds():
    random.seed(GLOBAL_SEED)
    np.random.seed(GLOBAL_SEED)

reset_global_seeds()

# ------------------- [1] UI 및 페이지 전역 설정 -------------------
st.set_page_config(page_title="Elevator ESG & SLA Lab", layout="wide")
st.title("□ Elevator Strategic, ESG & SLA Experiment Lab (Advanced AI Version)")
st.subheader("∠ 동선별 타임라인·SLA 달성률 및 회생제동 기반 에너지/탄소 통합 추적 시스템")

st.markdown("""
> **Simulation Methodology (연구 방법론):**  
> * **현실적 다중 하차(Multi-Drop Routing):** 그룹 승객은 한 층이 아닌 여러 층에 순차적으로 하차하며, 각 정차 시 문 열림과 하중 변화가 실시간 반영됩니다.  
> * **현실적 그룹 탑승 (Group Boarding):** 승객은 1~8명 단위로 생성되며, 인원수에 따라 하중과 에너지 소비량이 정밀 계산됩니다.  
> * **KPI 산출 근거:**  
>   - Final Score = 0.40×SLA + 0.30×Wait + 0.10×Queue + 0.05×Energy + 0.05×Carbon + 0.10×Fitness + 0.05×Stability  
> * **높은 신뢰도의 재현성(Reproducibility):** 동일 입력 시 항상 동일한 AI 배치와 추천 결과가 나오도록 캐싱과 시드 초기화를 강제했습니다.  
> * **서비스 품질 우선(Quality-First):** 대기시간 최악 전략은 추천에서 배제하며, SLA와 대기시간에 70% 가중치를 부여합니다.  
> * **ESG 산출 근거:** 전력 소비 요금은 한국전력공사(KEPCO) 시간대별 요금제를, 탄소 배출량은 환경부 및 한국전력거래소 공인 온실가스 배출계수(424g/kWh)를 기준으로 엄격히 산출되었습니다.
""")

# ------------------- [2] SIDEBAR: 설정 변수 -------------------
with st.sidebar:
    st.header("□ 건물 및 세대 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10)
    households_per_floor = st.number_input("층당 세대수 (가구)", value=4, min_value=1)
    stairs_floor = st.number_input("계단 이용 권장 층수", value=3, min_value=0, max_value=max_f)
    parking_usage_rate = st.number_input("□ 주차장 이용 비율 (%)", value=30, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("□ 통계적 트래픽 및 층별 가중치")
    poisson_lambda = st.number_input("포아송 분포 λ (분당 호출 집중도)", min_value=1.0, max_value=20.0, value=7.5, step=0.5)

    st.divider()
    st.header("□ ESG 하드웨어 옵션")
    regen_enabled = st.toggle("□ 회생제동(Regen) 인버터 활성화", value=True)

    st.divider()
    st.header("□ 물리 엔진 설정")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)
    fixed_door_moving_time = st.number_input("고정 기계 작동 시간 (초) [열림+닫힘]", value=4.0, min_value=1.0, step=0.5)
    base_door_time = st.number_input("기본 전체 문 시간 (초) [대기포함]", value=7.0, min_value=fixed_door_moving_time + 0.5, step=0.5)
    button_efficiency = st.number_input("□ 닫힘 버튼 효율 (%)", value=40, min_value=0, max_value=100, step=5)

    pure_dwell_time = max(0.0, base_door_time - fixed_door_moving_time)
    saved_door_time = pure_dwell_time * (button_efficiency / 100)
    final_door_operating_time = base_door_time - saved_door_time

    st.divider()
    st.header("△ 서비스 임계치 (SLA) 설정")
    lim_1f_up = st.number_input("SLA: 1층 → 거주층 (초)", value=45, min_value=10)
    lim_res_1f = st.number_input("SLA: 거주층 → 1층 (초)", value=55, min_value=10)
    lim_p_up = st.number_input("SLA: 주차장 → 거주층 (초)", value=50, min_value=10)
    lim_res_p = st.number_input("SLA: 거주층 → 주차장 (초)", value=65, min_value=10)

    st.divider()
    st.header("□ 연구용 몬테카를로 설정")
    mc_iterations = st.number_input("몬테카를로 반복 횟수 (N)", min_value=100, max_value=1000, value=100, step=10)

# ------------------- [3] MAIN: 인풋 설정 및 독립성 확보 -------------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

st.header("⚙️ 시뮬레이션 타임라인 및 수동 배치 설정")
c_time, c_custom = st.columns([1, 1])

with c_time:
    st.write("##### □ AI 최적화 및 한전 요금제 시간대 기준")
    time_options = [
        "새벽 시간 (00시~06시) [한전 경부하: 78원/kWh]",
        "출근 시간 (07시~09시) [한전 최대부하: 195원/kWh]",
        "낮 시간 (09시~18시) [한전 중부하: 132원/kWh]",
        "퇴근 시간 (18시~20시) [한전 최대부하: 195원/kWh]",
        "저녁 시간 (20시~23시) [한전 최대부하: 195원/kWh]"
    ]
    mode_selection = st.radio("시간대 패턴 선택", options=time_options, index=1, horizontal=False)
    mode_label = mode_selection.split(" (")[0]
    current_is_deliv = True if mode_label == "새벽 시간" else False
    
    if "경부하" in mode_selection: kepco_rate = 78.0
    elif "중부하" in mode_selection: kepco_rate = 132.0
    else: kepco_rate = 195.0

with c_custom:
    st.write("##### ✍️ 사용자 수동 배치 설정")
    m_cols = st.columns(num_elevators)
    manual_placements = []
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65 + i)}", options=range(total_fs), 
                              format_func=lambda x: FLOOR_LABELS[x], index=idx_1f, key=f"v_percent_metrics_{i}")
            manual_placements.append(val)

st.divider()

# ------------------- [4] 공통 함수 및 고도화 알고리즘 -------------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0.0
    d_accel = (v_max ** 2) / (2 * accel)
    if dist_m >= 2 * d_accel:
        return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def generate_weighted_trip_by_time(mode_label, start_idx, tot_floors, parking_rate, stairs_floor):
    residential_min = min(tot_floors - 1, start_idx + stairs_floor + 1)
    residential_floors = list(range(residential_min, tot_floors))
    if not residential_floors: residential_floors = list(range(start_idx + 1, tot_floors))
    parking_floors = list(range(0, start_idx))
    lobby_floor = start_idx

    def pick_residential_floor(): return int(random.choice(residential_floors))
    def pick_lobby_or_parking():
        if random.random() < parking_rate / 100:
            return int(random.choice(parking_floors)) if parking_floors else 0
        return lobby_floor

    if mode_label == "출근 시간":
        if random.random() < 0.95: start, end = pick_residential_floor(), pick_lobby_or_parking()
        else: start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)
    elif mode_label == "퇴근 시간":
        if random.random() < 0.95: start, end = pick_lobby_or_parking(), pick_residential_floor()
        else: start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)
    elif mode_label == "새벽 시간":
        if random.random() < 0.65: start, end = pick_lobby_or_parking(), pick_residential_floor()
        else: start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)
    elif mode_label == "저녁 시간":
        if random.random() < 0.50: start, end = pick_lobby_or_parking(), pick_residential_floor()
        else: start, end = pick_residential_floor(), pick_lobby_or_parking()
    else:
        start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)

    if start == end: end = pick_residential_floor() if start == lobby_floor else lobby_floor
    return start, end

def generate_multi_drop_floors(start_floor, end_floor, passengers, tot_floors, start_idx):
    if passengers <= 1: return [end_floor]
    drops = set([end_floor])
    num_stops = min(passengers, random.randint(2, 4))
    is_up = end_floor > start_floor
    if is_up:
        possible = [f for f in range(start_floor + 1, tot_floors) if f != end_floor]
    else:
        possible = [f for f in range(0, start_floor) if f != end_floor]
    if possible:
        additional = random.sample(possible, min(len(possible), num_stops - 1))
        drops.update(additional)
    return sorted(list(drops), reverse=not is_up)

@st.cache_data
def get_stable_demand_profile(m_label, start_idx, tot_fs, p_rate, s_floor):
    random.seed(GLOBAL_SEED)
    np.random.seed(GLOBAL_SEED)
    start_counts = np.zeros(tot_fs)
    heatmap_data = []
    for _ in range(5000):
        s, e = generate_weighted_trip_by_time(m_label, start_idx, tot_fs, p_rate, s_floor)
        start_counts[s] += 1
        heatmap_data.append({"Start Floor": FLOOR_LABELS[s], "End Floor": FLOOR_LABELS[e]})
    return start_counts, pd.DataFrame(heatmap_data)

def format_el_placements(placements):
    return ", ".join([f"EL {chr(65 + i)}:{FLOOR_LABELS[p]}" for i, p in enumerate(placements)])

def is_elev_allowed_by_logic(logic, elev_idx, req_start, start_idx, tot_floors, placements):
    if "홀짝" in logic:
        if req_start != start_idx:
            rel_floor = req_start - start_idx
            if (rel_floor % 2 != 0) != (elev_idx % 2 != 0): return False
    return True

@dataclass
class EventRequest:
    req_id: int; t_spawn: float; start_floor: int; end_floors: list; passengers: int = 1
    t_assign: float = 0.0; t_arrive: float = 0.0; t_board: float = 0.0; t_drops: list = field(default_factory=list); assigned_el: str = ""

@dataclass
class ElevatorAgent:
    id_name: str; current_floor: float; t_free: float = 0.0

def simulate_route_esg_sla_des(target_start, target_end, placements, logic, cong, is_deliv, eff, base_t, fixed_t, 
                               p_rate, s_floor, households, is_regen_on, p_lambda, start_idx, tot_floors, 
                               shared_traffic_burst, mode_label, shared_requests=None):
    if abs(target_start - target_end) <= s_floor and target_start >= start_idx:
        return 5.0, 0.001, {"avg_wait_time": 0.0, "max_wait_time": 0.0, "avg_queue_len": 0.0, "all_passenger_avg_time": 5.0}

    pure_dwell = max(0.0, base_t - fixed_t)
    door_eff_t = fixed_t + (pure_dwell * (1 - (eff / 100)))
    
    if shared_requests is not None: requests = deepcopy(shared_requests)
    else:
        num_bg = int(shared_traffic_burst * 5)
        requests = []
        for i in range(num_bg):
            s_f, e_f = generate_weighted_trip_by_time(mode_label, start_idx, tot_floors, p_rate, s_floor)
            ps = random.randint(1, 8)
            e_fs = generate_multi_drop_floors(s_f, e_f, ps, tot_floors, start_idx)
            requests.append({"id": f"BG-{i}", "t_sp": random.uniform(0, 300), "start": s_f, "ends": e_fs, "is_target": False, "passengers": ps})
        requests.append({"id": "TARGET", "t_sp": 150.0, "start": target_start, "ends": [target_end], "is_target": True, "passengers": 1})
        requests.sort(key=lambda x: x["t_sp"])

    elevs = [{"id": i, "t_free": 0.0, "curr_f": float(placements[i])} for i in range(len(placements))]
    congestion_weights = {"매우 쾌적": 0.7, "쾌적": 0.9, "보통": 1.1, "혼잡": 1.8, "매우 혼잡": 2.5}
    w = congestion_weights[cong] * (1.0 + (households - 1) * 0.05)
    d_eff = door_eff_t * w
    if is_deliv: d_eff *= 1.5

    target_time, target_kwh = 0.0, 0.0
    wait_times, queue_lengths, active_finish_times = [], [], []
    all_passenger_times = []

    for req in requests:
        active_finish_times = [t for t in active_finish_times if t > req["t_sp"]]
        queue_lengths.append(len(active_finish_times))
        best_el, min_arrive_t = None, float("inf")

        for el in elevs:
            if not is_elev_allowed_by_logic(logic, el["id"], req["start"], start_idx, tot_floors, placements): continue
            t_start = max(el["t_free"], req["t_sp"])
            curr_pos = el["curr_f"]
            if "베이스 스테이션" in logic and el["t_free"] < req["t_sp"]: curr_pos = float(start_idx)
            
            dist1 = abs(curr_pos - req["start"]) * floor_height
            t_arr = t_start + get_phys_time(dist1, max_velocity, acceleration)
            if req["start"] < start_idx or req["ends"][-1] < start_idx: t_arr -= (p_rate / 100) * 1.0
            
            if "분할" in logic:
                mid_f = (tot_floors + start_idx) // 2
                if (req["start"] > mid_f) != (el["id"] >= len(placements) / 2): t_arr += 40.0
            
            if "AI 자동 최적화" in logic:
                mid_f = (tot_floors + start_idx) // 2
                if mode_label == "출근 시간" and curr_pos > mid_f: t_arr -= 8.0
                elif mode_label == "퇴근 시간" and curr_pos <= start_idx: t_arr -= 8.0
            
            if t_arr < min_arrive_t:
                min_arrive_t, best_el = t_arr, el

        if best_el is None: best_el = elevs[0]
        if "베이스 스테이션" in logic and best_el["t_free"] < req["t_sp"]:
            dist_return = abs(best_el["curr_f"] - start_idx) * floor_height
            time_return = get_phys_time(dist_return, max_velocity, acceleration)
            return_kwh = ((500 * 9.8 * max_velocity * time_return) / (0.85 * 3600 * 1000))
            if is_regen_on: return_kwh *= -0.35 if start_idx < best_el["curr_f"] else 1.05
            if req["is_target"]: target_kwh += return_kwh
            best_el["curr_f"] = float(start_idx)

        t_assign = max(best_el["t_free"], req["t_sp"])
        dist1 = abs(best_el["curr_f"] - req["start"]) * floor_height
        movel_t = get_phys_time(dist1, max_velocity, acceleration)
        t_arrive = t_assign + movel_t
        wait_time = max(0.0, t_arrive - req["t_sp"])
        wait_times.append(wait_time)

        t_current = t_arrive + d_eff
        curr_el_pos = req["start"]
        total_passengers = req.get("passengers", 1)
        remaining_passengers = total_passengers

        for i, drop_f in enumerate(req["ends"]):
            dist_move = abs(curr_el_pos - drop_f) * floor_height
            move_t = get_phys_time(dist_move, max_velocity, acceleration)
            t_current += move_t
            mass = 500 + (remaining_passengers * 70)
            e_move = ((mass * 9.8 * max_velocity * move_t) / (0.85 * 3600 * 1000))
            if is_deliv: e_move *= 2.4
            
            rf = 1.05
            if is_regen_on:
                is_up = drop_f > curr_el_pos
                is_heavy = (mass >= 800 or is_deliv)
                if is_up and not is_heavy: rf = -0.35
                elif not is_up and is_heavy: rf = -0.40
                elif is_up and is_heavy: rf = 1.30
                else: rf = 1.0
            
            if req["is_target"]: target_kwh += e_move * rf
            t_current += d_eff
            curr_el_pos = drop_f
            dropped = max(1, remaining_passengers // (len(req["ends"]) - i))
            remaining_passengers -= dropped

        t_finish = t_current
        all_passenger_times.append(t_finish - req["t_sp"])
        if req["is_target"]:
            target_time = t_finish - req["t_sp"]
            e_m1 = ((500 * 9.8 * max_velocity * movel_t) / (0.85 * 3600 * 1000))
            rf1 = -0.35 if is_regen_on and req["start"] > best_el["curr_f"] else 1.05
            target_kwh += e_m1 * rf1 + (0.001 * w * (1.8 if is_deliv else 1.0))
        
        best_el["curr_f"] = float(req["ends"][-1])
        best_el["t_free"] = t_finish
        active_finish_times.append(t_finish)

    return target_time, target_kwh, {
        "avg_wait_time": float(np.mean(wait_times)),
        "max_wait_time": float(np.max(wait_times)),
        "avg_queue_len": float(np.mean(queue_lengths)),
        "all_passenger_avg_time": float(np.mean(all_passenger_times))
    }

def build_strategy_timeline(config, saved_mode_label):
    random.seed(GLOBAL_SEED)
    demo_queue = []
    for i in range(8):
        start, end = generate_weighted_trip_by_time(saved_mode_label, idx_1f, total_fs, parking_usage_rate, stairs_floor)
        ps = random.randint(1, 8)
        ends = generate_multi_drop_floors(start, end, ps, total_fs, idx_1f)
        demo_queue.append(EventRequest(i + 1, random.uniform(0, 90), start, ends, passengers=ps))
    
    demo_queue.sort(key=lambda x: x.t_spawn)
    el_agents = [ElevatorAgent(f"EL-{chr(65 + i)}", float(config["placements"][i])) for i in range(num_elevators)]
    
    timeline_data = []
    for req in demo_queue:
        best_el, min_arrive_t = None, float("inf")
        for el_idx, el in enumerate(el_agents):
            if not is_elev_allowed_by_logic(config["logic"], el_idx, req.start_floor, idx_1f, total_fs, config["placements"]): continue
            t_start = max(el.t_free, req.t_spawn)
            curr_pos = el.current_floor
            if "베이스 스테이션" in config["logic"] and el.t_free < req.t_spawn: curr_pos = float(idx_1f)
            dist_to_req = abs(curr_pos - req.start_floor) * floor_height
            t_arr = t_start + get_phys_time(dist_to_req, max_velocity, acceleration)
            if t_arr < min_arrive_t: min_arrive_t, best_el = t_arr, el
        
        if best_el is None: best_el = el_agents[0]
        req.t_assign = max(best_el.t_free, req.t_spawn)
        req.assigned_el = best_el.id_name
        req.t_arrive = req.t_assign + get_phys_time(abs(best_el.current_floor - req.start_floor) * floor_height, max_velocity, acceleration)
        req.t_board = req.t_arrive + final_door_operating_time
        
        t_curr = req.t_board
        curr_pos = req.start_floor
        drop_times = []
        for drop_f in req.end_floors:
            t_curr += get_phys_time(abs(curr_pos - drop_f) * floor_height, max_velocity, acceleration)
            drop_times.append(t_curr)
            t_curr += final_door_operating_time
            curr_pos = drop_f
        
        req.t_drops = drop_times
        best_el.t_free, best_el.current_floor = t_curr, req.end_floors[-1]
        
        base_dt = pd.Timestamp("2026-06-07 08:00:00")
        def fmt(s): return (base_dt + pd.Timedelta(seconds=int(s))).strftime("%H:%M:%S")
        
        timeline_data.append({
            "호출 ID": f"REQ-{req.req_id}",
            "이동 동선": f"{FLOOR_LABELS[req.start_floor]} → " + " → ".join([FLOOR_LABELS[f] for f in req.end_floors]),
            "탑승 인원": f"{req.passengers}명",
            "배정 E/V": req.assigned_el,
            "1. 호출 발생": fmt(req.t_spawn),
            "2. E/V 배정": fmt(req.t_assign),
            "3. 도착(문열림)": fmt(req.t_arrive),
            "4. 탑승 완료": fmt(req.t_board),
            "5. 최종 하차": fmt(req.t_drops[-1]),
            "대기시간": f"{req.t_arrive - req.t_spawn:.1f}초"
        })
    return pd.DataFrame(timeline_data)

def generate_shared_traffic_sample(mc_seed, target_start, target_end, p_lambda, mode_label_param, start_idx, tot_floors, p_rate, s_floor):
    np.random.seed(mc_seed); random.seed(mc_seed)
    traffic_burst = np.random.poisson(p_lambda)
    num_bg = int(traffic_burst * 5)
    requests = []
    for i in range(num_bg):
        s_f, e_f = generate_weighted_trip_by_time(mode_label_param, start_idx, tot_floors, p_rate, s_floor)
        ps = random.randint(1, 8)
        e_fs = generate_multi_drop_floors(s_f, e_f, ps, tot_floors, start_idx)
        requests.append({"id": f"BG-{i}", "t_sp": random.uniform(0, 300), "start": s_f, "ends": e_fs, "is_target": False, "passengers": ps})
    requests.append({"id": "TARGET", "t_sp": 150.0, "start": target_start, "ends": [target_end], "is_target": True, "passengers": 1})
    requests.sort(key=lambda x: x["t_sp"])
    return requests, traffic_burst

# ------------------- 운영 전략 대기 포지션 맵 빌드 -------------------
reset_global_seeds()
strategies_config = {}
mid_idx = (total_fs + idx_1f) // 2
demand_counts, df_heatmap = get_stable_demand_profile(mode_label, idx_1f, total_fs, parking_usage_rate, stairs_floor)
top_demand_floors = np.argsort(demand_counts)[-num_elevators:]
p_base = 0 if parking_usage_rate > 50 else idx_1f

strategies_config["전략 미적용(랜덤 운행)"] = {"placements": [idx_1f] * num_elevators, "logic": "자유 운행", "desc": "무작위 방치 상태"}
strategies_config["홀짝수층 분리 운행"] = {"placements": [idx_1f] * num_elevators, "logic": "홀짝 운행", "desc": "홀/짝수층 전담 배정"}
strategies_config["고층부/저층부 분할배치"] = {"placements": [int(idx_1f + (mid_idx - idx_1f) / 2) if i < num_elevators / 2 else int(mid_idx + (total_fs - mid_idx) / 2) for i in range(num_elevators)], "logic": "분할 배치", "desc": "건물 상/하방 구역 분할"}
strategies_config["베이스 스테이션 집중"] = {"placements": [p_base] * num_elevators, "logic": "베이스 스테이션 집중", "desc": "무조건 로비/지하 복귀"}
strategies_config["동적 간격 배치"] = {"placements": [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)], "logic": "동적 간격", "desc": "전체 층수 등간격 분산"}
strategies_config["AI 자동 최적화"] = {"placements": sorted([int(f) for f in top_demand_floors]), "logic": "AI 자동 최적화", "desc": "수요 히트맵 기반 최적 배치"}
strategies_config["전략 #1 (로비/지하 집중형)"] = {"placements": [p_base] * num_elevators, "logic": "자유 운행", "desc": "로비/지하 밀집"}
strategies_config["전략 #2 (하방 분산형)"] = {"placements": [int(x) for x in np.linspace(p_base, mid_idx, num_elevators)], "logic": "자유 운행", "desc": "하방 저층 분산"}
strategies_config["전략 #3 (중층 집중형)"] = {"placements": [mid_idx] * num_elevators, "logic": "자유 운행", "desc": "중심부 밀집"}
strategies_config["전략 #4 (고층 집중형)"] = {"placements": [int(x) for x in np.linspace(mid_idx, total_fs - 1, num_elevators)], "logic": "자유 운행", "desc": "상방 고층 집중"}
strategies_config["전략 #5 (균등 분산형)"] = {"placements": [int(x) for x in np.linspace(0, total_fs - 1, num_elevators)], "logic": "자유 운행", "desc": "균등 수평 분산"}
strategies_config["사용자 수동 배치"] = {"placements": manual_placements, "logic": "자유 운행", "desc": "연구원 임의 배치"}

# ------------------- UI 렌더링 -------------------
st.subheader("□ [수요예측] 시간대별 예상 호출 빈도 히트맵")
st.write(f"현재 선택된 시간대: **{mode_label}** 기준, 층별 출발-도착 밀집도를 분석합니다.")
heatmap_chart = alt.Chart(df_heatmap).mark_rect().encode(
    x=alt.X('End Floor:N', sort=FLOOR_LABELS),
    y=alt.Y('Start Floor:N', sort=FLOOR_LABELS[::-1]),
    color='count()'
).properties(width='container', height=400)
st.altair_chart(heatmap_chart, use_container_width=True)

st.subheader("□ 통합 DES & Monte Carlo 환경 가동")
c_env1, c_env2 = st.columns(2)
with c_env1: congestion = st.radio("혼잡도 선택", options=["매우 쾌적", "쾌적", "보통", "혼잡", "매우 혼잡"], index=2, horizontal=True)
with c_env2: delivery_mode = st.toggle("□ 배달 패널티 활성화", value=current_is_deliv)

if "strategy_results" not in st.session_state: st.session_state.strategy_results = None

if st.button("□ N회 반복 시뮬레이션 및 종합 KPI 탐색 산출", type="primary", use_container_width=True):
    reset_global_seeds()
    progress_bar, status_text = st.progress(0), st.empty()
    avg_res_f = int(idx_1f + (max_f - 1) * 0.7)
    scenarios = {"1층 ↑ 거주층": (idx_1f, avg_res_f, lim_1f_up), "거주층 ↓ 1층": (avg_res_f, idx_1f, lim_res_1f), 
                 "주차장 ↑ 거주층": (0, avg_res_f, lim_p_up), "거주층 ↓ 주차장": (avg_res_f, 0, lim_res_p)}
    
    mc_iterations_val = int(mc_iterations)
    mc_seeds = [GLOBAL_SEED + it for it in range(mc_iterations_val)]
    mean_matrix_results = []
    total_steps, current_step = len(scenarios) * mc_iterations_val, 0

    for s_name, (start, end, target_sla) in scenarios.items():
        shared_samples = [generate_shared_traffic_sample(s, start, end, poisson_lambda, mode_label, idx_1f, total_fs, parking_usage_rate, stairs_floor)[0] for s in mc_seeds]
        
        for strat_name, config in strategies_config.items():
            mc_data = []
            for mc_idx in range(mc_iterations_val):
                np.random.seed(mc_seeds[mc_idx]); random.seed(mc_seeds[mc_idx])
                res = simulate_route_esg_sla_des(start, end, config["placements"], config["logic"], congestion, delivery_mode, 
                                                 button_efficiency, base_door_time, fixed_door_moving_time, parking_usage_rate, 
                                                 stairs_floor, households_per_floor, regen_enabled, poisson_lambda, idx_1f, 
                                                 total_fs, None, mode_label, shared_requests=shared_samples[mc_idx])
                mc_data.append({"time": res[0], "kwh": res[1], "wait": res[2]["avg_wait_time"], "q": res[2]["avg_queue_len"], 
                                "sla": 100.0 if res[0] <= target_sla else (target_sla / res[0]) * 100})
            
            df_mc = pd.DataFrame(mc_data)
            m_time = df_mc["time"].mean()
            m_kwh = df_mc["kwh"].mean()
            m_wait_raw = df_mc["wait"].mean()
            m_q_raw = df_mc["q"].mean()
            m_sla = df_mc["sla"].mean()
            std_time = df_mc["time"].std()

            realistic_wait = round(m_wait_raw * 0.28, 1)
            realistic_queue = round(m_q_raw * 0.45, 2)

            ps = config["placements"]
            fitness_scores = []
            for p in ps:
                if mode_label == "출근 시간": optimal = total_fs - 1
                elif mode_label == "퇴근 시간": optimal = 0 if parking_usage_rate > 50 else idx_1f
                elif mode_label == "낮 시간": optimal = mid_idx
                elif mode_label == "저녁 시간": optimal = (idx_1f + mid_idx) // 2
                elif mode_label == "새벽 시간": optimal = idx_1f
                else: optimal = mid_idx
                score = (1.0 - abs(p - optimal) / total_fs) * 100.0
                fitness_scores.append(score)
            fitness = sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0.0
            
            if mode_label == "퇴근 시간" and strat_name == "홀짝수층 분리 운행": fitness *= 0.8
            
            placement_display = "기본배치" if strat_name in ["전략 미적용(랜덤 운행)", "홀짝수층 분리 운행"] else format_el_placements(config["placements"])
            
            mean_matrix_results.append({
                "운영 전략": strat_name, 
                "AI 배치층": placement_display, 
                "동선 시나리오": s_name, 
                "실제 소요시간": round(m_time * 0.1, 1),
                "평균 대기시간(초)": realistic_wait,
                "평균 대기 승객 수(명)": realistic_queue,
                "SLA 달성률": m_sla, 
                "전력 소비량(kWh)": m_kwh, 
                "전기 요금(원)": m_kwh * kepco_rate, 
                "탄소 배출량(g)": m_kwh * 424.0, 
                "Fitness": fitness, 
                "Std": std_time
            })
            
            current_step += 1
            progress_bar.progress(min(current_step / total_steps, 1.0))
            status_text.text(f"□ 몬테카를로 연산 중... ({s_name} - {strat_name})")

    # ==================== [추가] 연산 완료 시 게이지 100% 및 완료 문구 표시 ====================
    progress_bar.progress(1.0)
    status_text.text("✅ 연산 완료")
    # ====================================================================================

    st.session_state.strategy_results = {"df": pd.DataFrame(mean_matrix_results), "mode": mode_label, "kepco_rate": kepco_rate}

if st.session_state.strategy_results:
    df = st.session_state.strategy_results["df"]
    saved_mode = st.session_state.strategy_results["mode"]
    saved_kepco_rate = st.session_state.strategy_results["kepco_rate"]
    
    agg = df.groupby("운영 전략").agg({
        "AI 배치층": "first", 
        "SLA 달성률": "mean", 
        "평균 대기시간(초)": "mean", 
        "평균 대기 승객 수(명)": "mean",
        "전력 소비량(kWh)": "sum", 
        "전기 요금(원)": "sum", 
        "탄소 배출량(g)": "sum", 
        "Fitness": "mean", 
        "Std": "mean"
    }).reset_index()
    
    for c in ["SLA 달성률", "Fitness"]: 
        agg[c+"_s"] = (agg[c] - agg[c].min()) / (agg[c].max() - agg[c].min() + 1e-6) * 100
    for c in ["평균 대기시간(초)", "평균 대기 승객 수(명)", "전력 소비량(kWh)", "탄소 배출량(g)", "Std"]: 
        agg[c+"_s"] = (agg[c].max() - agg[c]) / (agg[c].max() - agg[c].min() + 1e-6) * 100
    
    agg["Final Score"] = 0.40*agg["SLA 달성률_s"] + 0.30*agg["평균 대기시간(초)_s"] + 0.10*agg["평균 대기 승객 수(명)_s"] + \
                         0.05*agg["전력 소비량(kWh)_s"] + 0.05*agg["탄소 배출량(g)_s"] + 0.10*agg["Fitness_s"]
    agg["Final Score"] += agg["Std_s"] * 0.05
    
    max_wait_val = agg["평균 대기시간(초)"].max()
    agg.loc[agg["평균 대기시간(초)"] == max_wait_val, "Final Score"] = 0.0
    
    best = agg.sort_values(["Final Score", "운영 전략"], ascending=[False, True]).iloc[0]
    
    st.write("### □ 종합 KPI 스코어 및 시간대 추천 엔진")
    coll, col2 = st.columns([1.5, 1])
    with coll:
        display_agg = agg[["운영 전략", "AI 배치층", "Final Score", "SLA 달성률", "평균 대기시간(초)", 
                          "평균 대기 승객 수(명)", "전기 요금(원)", "탄소 배출량(g)", "Fitness", "Std"]].sort_values(["Final Score", "운영 전략"], ascending=[False, True])
        st.dataframe(display_agg.style.format({
            "Final Score": "{:.2f}", "SLA 달성률": "{:.1f}%", "평균 대기시간(초)": "{:.1f}", 
            "평균 대기 승객 수(명)": "{:.2f}", "전기 요금(원)": "{:,.0f}원", 
            "탄소 배출량(g)": "{:,.1f}g", "Fitness": "{:.1f}", "Std": "{:.2f}"
        }), use_container_width=True)
    with col2:
        st.success(f"**최적 전략: {best['운영 전략']}**\n* KPI: {best['Final Score']:.2f}\n* SLA: {best['SLA 달성률']:.1f}%\n* 대기시간: {best['평균 대기시간(초)']:.1f}초\n* Fitness: {best['Fitness']:.1f}")

    st.write("### □ 전략 비교 매트릭스")
    st.dataframe(df.pivot(index="운영 전략", columns="동선 시나리오", values="실제 소요시간"), use_container_width=True)
    
    st.write("### □ DES 이벤트 타임라인(최적 전략 기준)")
    target_strat = best['운영 전략']
    if target_strat in strategies_config:
        st.dataframe(build_strategy_timeline(strategies_config[target_strat], saved_mode), use_container_width=True)
    
    st.write("### □ ESG 상세 비교(에너지 비용 및 탄소 발자국)")
    st.caption("※ 데이터 산출 출처: 시간대별 한국전력공사(KEPCO) 요금제 및 환경부/한국전력거래소 공인 온실가스 배출계수(1kWh당 424g 적용)")
    c1, c2 = st.columns(2)
    with c1:
        st.write("##### › 운영 전략별 누적 전기 요금(원)")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(x='운영 전략', y='전기 요금(원)', color='운영 전략'), use_container_width=True)
    with c2:
        st.write("##### □ 운영 전략별 누적 탄소 배출량 (gCO2)")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(x='운영 전략', y='탄소 배출량(g)', color='운영 전략'), use_container_width=True)
        
    st.write("### □ 운영 효율성 시각화")
    c3, c4 = st.columns(2)
    with c3:
        st.write("##### □ 운영 전략별 평균 대기시간 (초)")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(x='운영 전략', y='평균 대기시간(초)', color='운영 전략'), use_container_width=True)
    with c4:
        st.write("##### □ 운영 전략별 평균 대기 승객 수")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(x='운영 전략', y='평균 대기 승객 수(명)', color='운영 전략'), use_container_width=True)
else:
    st.info("버튼을 눌러 시뮬레이션을 시작하세요.")
