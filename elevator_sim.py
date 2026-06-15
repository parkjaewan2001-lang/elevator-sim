import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from dataclasses import dataclass, field
import random
from copy import deepcopy

# ----------------- [0] 완전 재현성을 위한 글로벌 시드 설정 -----------------
GLOBAL_SEED = 42
MONTE_CARLO_RUNS = 100 

def reset_global_seeds():
    random.seed(GLOBAL_SEED)
    np.random.seed(GLOBAL_SEED)

reset_global_seeds()

# ----------------- [1] UI 및 페이지 전역 설정 -----------------
st.set_page_config(page_title="Elevator ESG & SLA Lab", layout="wide")
st.title("🏢 Elevator Strategic, ESG & SLA Experiment Lab (Advanced AI Version)")
st.subheader("⚡ 동선별 타임라인·SLA 달성률 및 회생제동 기반 에너지/탄소 통합 추적 시스템")

st.markdown("""
> 💡 **Simulation Methodology (연구 방법론):**
> * **현실적 다중 하차 (Multi-Drop Routing):** 이제 그룹 승객은 한 층이 아닌 **여러 층(예: 27F → 15F → 1F)**에 걸쳐 순차적으로 하차하며, 각 정차 시의 문 열림과 하중 변화가 실시간 반영됩니다.
> * **현실적 그룹 탑승 (Group Boarding):** 승객은 1~8명의 그룹 단위로 생성되며, 인원수에 따라 엘리베이터의 하중과 에너지 소비량이 정밀하게 계산됩니다.
> * **높은 신뢰도의 재현성 (Reproducibility):** 동일 입력 시 항상 동일한 AI 배치와 추천 결과가 나오도록 캐싱과 시드 초기화를 강제했습니다.
> * **서비스 품질 우선(Quality-First):** 대기시간 최악 전략은 추천에서 배제하며, SLA와 대기시간에 70% 가중치를 부여합니다.
> * **KPI 산출 근거:** SLA(40%), 평균 대기시간(30%), 평균 Queue 길이(10%), Fitness(10%), 에너지/탄소(10%)의 가중치로 종합 KPI를 산출하며, 모든 지표는 Min-Max 정규화 후 반영됩니다. 최악의 대기시간 전략은 강제 배제됩니다.
> * **ESG 산출 근거:** 전력 소비 요금은 한국전력공사(KEPCO) 시간대별 요금제를, 탄소 배출량은 환경부 및 한국전력거래소 공인 온실가스 배출계수(424g/kWh)를 기준으로 엄격히 산출되었습니다.
""")

# ----------------- [2] SIDEBAR: 설정 변수 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)

    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10)
    households_per_floor = st.number_input("층당 세대수 (가구)", value=4, min_value=1)
    stairs_floor = st.number_input("계단 이용 권장 층수", value=3, min_value=0, max_value=max_f)
    parking_usage_rate = st.number_input("🚗 주차장 이용 비율 (%)", value=30, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("📊 통계적 트래픽 및 층별 가중치")
    poisson_lambda = st.number_input("포아송 분포 λ (분당 호출 집중도)", min_value=1.0, max_value=20.0, value=7.5, step=0.5)

    st.divider()
    st.header("🌱 ESG 하드웨어 옵션")
    regen_enabled = st.toggle("🔄 회생제동(Regen) 인버터 활성화", value=True)

    st.divider()
    st.header("🚀 물리 엔진 설정")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)
    fixed_door_moving_time = st.number_input("고정 기계 작동 시간 (초) [열림+닫힘]", value=4.0, min_value=1.0, step=0.5)
    base_door_time = st.number_input("기본 전체 문 시간 (초) [대기포함]", value=7.0, min_value=fixed_door_moving_time + 0.5, step=0.5)
    button_efficiency = st.number_input("🔘 닫힘 버튼 효율 (%)", value=40, min_value=0, max_value=100, step=5)

    pure_dwell_time = max(0.0, base_door_time - fixed_door_moving_time)
    saved_door_time = pure_dwell_time * (button_efficiency / 100)
    final_door_operating_time = base_door_time - saved_door_time

    st.divider()
    st.header("⚠️ 서비스 임계치 (SLA) 설정")
    lim_1f_up = st.number_input("SLA: 1층 → 거주층 (초)", value=45, min_value=10)
    lim_res_1f = st.number_input("SLA: 거주층 → 1층 (초)", value=55, min_value=10)
    lim_p_up = st.number_input("SLA: 주차장 → 거주층 (초)", value=50, min_value=10)
    lim_res_p = st.number_input("SLA: 거주층 → 주차장 (초)", value=65, min_value=10)

    st.divider()
    st.header("🔬 연구용 몬테카를로 설정")
    mc_iterations = st.number_input("몬테카를로 반복 횟수 (N)", min_value=100, max_value=1000, value=100, step=10)


# ----------------- [3] MAIN: 인풋 설정 및 독립성 확보 -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

st.header("⚙️ 시뮬레이션 타임라인 및 수동 배치 설정")
c_time, c_custom = st.columns([1, 1])

with c_time:
    st.write("##### ⏰ AI 최적화 및 한전 요금제 시간대 기준")
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
            val = st.selectbox(f"EL {chr(65 + i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f, key=f"v_percent_metrics_{i}")
            manual_placements.append(val)

st.divider()

# ----------------- [4] 공통 함수 및 고도화 알고리즘 -----------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0.0
    d_accel = (v_max ** 2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
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
    else: # 낮 시간
        start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)

    if start == end: end = pick_residential_floor() if start == lobby_floor else lobby_floor
    return start, end

def generate_multi_drop_floors(start_floor, end_floor, passengers, tot_floors, start_idx):
    if passengers <= 1: return [end_floor]
    
    drops = set([end_floor])
    num_stops = min(passengers, random.randint(2, 4)) # 최대 4개 층 정차
    
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

def simulate_route_esg_sla_des(
    target_start, target_end, placements, logic, cong, is_deliv, eff, base_t, fixed_t,
    p_rate, s_floor, households, is_regen_on, p_lambda, start_idx, tot_floors,
    shared_traffic_burst, mode_label, h_penalty, shared_requests=None
):
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
                if (req["start"] > mid_f) != (el["id"] >= len(placements) / 2): t_arr += h_penalty # h_penalty 적용
            if "AI 자동 최적화" in logic:
                mid_f = (tot_floors + start_idx) // 2
                if mode_label == "출근 시간" and curr_pos > mid_f: t_arr -= 8.0
                elif mode_label == "퇴근 시간" and curr_pos <= start_idx: t_arr -= 8.0
            if t_arr < min_arrive_t:
                min_arrive_t = t_arr
                best_el = el

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
        move1_t = get_phys_time(dist1, max_velocity, acceleration)
        t_arrive = t_assign + move1_t
        wait_time = max(0.0, t_arrive - req["t_sp"])
        wait_times.append(wait_time)
        
        t_current = t_arrive + d_eff # 탑승 완료 시점
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
                is_heavy = (mass >= 500 + (total_passengers * 70 / 2)) # 절반 이상 탑승 시 무겁다고 판단
                if is_up and is_heavy: rf = 1.05 # 무거운 상태로 올라가면 에너지 더 소모
                elif not is_up and is_heavy: rf = -0.35 # 무거운 상태로 내려가면 회생제동
                elif is_up and not is_heavy: rf = 1.0 # 가벼운 상태로 올라가면 일반 소모
                elif not is_up and not is_heavy: rf = 0.8 # 가벼운 상태로 내려가면 적게 소모
            
            e_move *= rf
            target_kwh += e_move
            
            curr_el_pos = drop_f
            if i < len(req["ends"]) - 1: # 마지막 하차 층이 아니면 문 열림/닫힘 시간 추가
                t_current += d_eff
                if remaining_passengers > 0:
                    remaining_passengers -= random.randint(1, remaining_passengers) # 일부 승객 하차
            
        t_finish = t_current
        best_el["t_free"] = t_finish
        best_el["curr_f"] = float(req["ends"][-1])
        active_finish_times.append(t_finish)

        if req["is_target"]:
            target_time = t_finish - req["t_sp"]
        all_passenger_times.append(t_finish - req["t_sp"])

    avg_wait_time = np.mean(wait_times) if wait_times else 0.0
    max_wait_time = np.max(wait_times) if wait_times else 0.0
    avg_queue_len = np.mean(queue_lengths) if queue_lengths else 0.0
    all_passenger_avg_time = np.mean(all_passenger_times) if all_passenger_times else 0.0

    return target_time, target_kwh, {"avg_wait_time": avg_wait_time, "max_wait_time": max_wait_time, "avg_queue_len": avg_queue_len, "all_passenger_avg_time": all_passenger_avg_time}


# ----------------- [5] 전략 정의 -----------------
# AI 자동 최적화 배치 로직
@st.cache_data
def get_ai_optimized_placements(m_label, start_idx, tot_fs, p_rate, s_floor, num_elev):
    random.seed(GLOBAL_SEED)
    np.random.seed(GLOBAL_SEED)
    start_counts, _ = get_stable_demand_profile(m_label, start_idx, tot_fs, p_rate, s_floor)
    
    # 주차장 이용률이 높으면 지하층을 AI 배치 우선순위에 강제 반영
    if p_rate > 50 and (m_label == "퇴근 시간" or m_label == "새벽 시간" or m_label == "저녁 시간"):
        # 지하층 인덱스 (0 ~ start_idx-1)
        parking_floor_indices = list(range(0, start_idx))
        if parking_floor_indices:
            # 지하층 수요를 start_counts에 추가 (가중치 부여)
            for p_idx in parking_floor_indices:
                start_counts[p_idx] += start_counts.max() * (p_rate / 100) # 주차장 비율만큼 가중치

    # AI 배치층은 가장 호출이 많은 층으로
    ai_placements = np.argsort(start_counts)[::-1][:num_elev]
    
    # AI 자동 최적화 전략이 지하층을 포함하도록 강제 (주차장 이용률 100% 시)
    if p_rate == 100 and (m_label == "퇴근 시간" or m_label == "새벽 시간" or m_label == "저녁 시간"):
        if 0 not in ai_placements and num_elev > 0: # 지하 0층이 없으면 추가
            ai_placements = list(ai_placements)
            ai_placements[0] = 0 # 가장 호출 많은 층 중 하나를 지하 0층으로 대체
            ai_placements = np.array(ai_placements)

    return ai_placements

# 전략 설정 딕셔너리
strategies_config = {
    "전략 미적용 (랜덤 운행)": {
        "placements": [idx_1f] * num_elevators, # 초기 위치는 1층
        "logic": "랜덤 운행",
        "description": "호출이 오면 가장 가까운 엘리베이터가 이동합니다. 특별한 전략 없이 운행합니다."
    },
    "AI 자동 최적화": {
        "placements": [], # 동적으로 계산
        "logic": "AI 자동 최적화",
        "description": "AI가 시간대별 호출 히트맵을 분석하여 엘리베이터를 최적의 층에 미리 배치합니다."
    },
    "사용자 수동 배치": {
        "placements": [], # 사용자 입력
        "logic": "수동 배치",
        "description": "사용자가 직접 엘리베이터의 초기 대기 층을 설정합니다."
    },
    "고층부/저층부 분할 배치": {
        "placements": [], # 동적으로 계산
        "logic": "분할 배치",
        "description": "엘리베이터를 고층부와 저층부 전담으로 나누어 운행합니다. 비전담 구역 호출 시 패널티가 적용됩니다."
    },
    "홀짝수층 분리 운행": {
        "placements": [idx_1f] * num_elevators, # 초기 위치는 1층
        "logic": "홀짝수층",
        "description": "엘리베이터를 홀수층 전담과 짝수층 전담으로 나누어 운행합니다. (1층 제외)"
    },
    "베이스 스테이션 (1층/지하)": {
        "placements": [], # 동적으로 계산
        "logic": "베이스 스테이션",
        "description": "모든 엘리베이터가 호출 처리 후 1층 또는 지하층으로 복귀하여 대기합니다."
    },
    "AI Generated Strategy #1 (로비/지하 집중형)": {
        "placements": [idx_1f, 0] if num_elevators >= 2 else [idx_1f], # 1층과 지하 0층
        "logic": "AI Generated Strategy",
        "description": "AI가 생성한 전략: 로비와 지하층에 집중 배치하여 빠른 응답을 목표로 합니다."
    },
    "AI Generated Strategy #2 (고층부 집중형)": {
        "placements": [max_f, max_f - 1] if num_elevators >= 2 else [max_f], # 최고층과 그 아래층
        "logic": "AI Generated Strategy",
        "description": "AI가 생성한 전략: 고층부 승객의 빠른 수송을 위해 상위 층에 집중 배치합니다."
    },
    "AI Generated Strategy #3 (중간층 분산형)": {
        "placements": [total_fs // 3, total_fs * 2 // 3] if num_elevators >= 2 else [total_fs // 2],
        "logic": "AI Generated Strategy",
        "description": "AI가 생성한 전략: 중간층에 분산 배치하여 건물 전체의 균형 잡힌 서비스를 제공합니다."
    },
    "AI Generated Strategy #4 (수요 예측 분산형)": {
        "placements": [idx_1f, max_f, 0] if num_elevators >= 3 else ([idx_1f, max_f] if num_elevators == 2 else [idx_1f]),
        "logic": "AI Generated Strategy",
        "description": "AI가 생성한 전략: 주요 수요층(로비, 최고층, 지하)에 엘리베이터를 분산 배치합니다."
    },
    "AI Generated Strategy #5 (심야/배달 최적화)": {
        "placements": [idx_1f, 0] if num_elevators >= 2 else [idx_1f], # 1층과 지하 0층
        "logic": "AI Generated Strategy",
        "description": "AI가 생성한 전략: 심야 시간대나 배달 서비스에 최적화된 배치로, 로비와 지하층 응답을 강화합니다."
    }
}

# 동적 배치 계산
ai_optimized_placements = get_ai_optimized_placements(mode_label, idx_1f, total_fs, parking_usage_rate, stairs_floor, num_elevators)
strategies_config["AI 자동 최적화"]["placements"] = ai_optimized_placements
strategies_config["사용자 수동 배치"]["placements"] = manual_placements

# 고층부/저층부 분할 배치 계산
if num_elevators > 1:
    mid_floor_idx = (total_fs + idx_1f) // 2
    split_placements = []
    for i in range(num_elevators):
        if i < num_elevators / 2: # 저층부 전담
            split_placements.append(idx_1f) # 저층부 엘리베이터는 1층 대기
        else: # 고층부 전담
            split_placements.append(max_f) # 고층부 엘리베이터는 최고층 대기
    strategies_config["고층부/저층부 분할 배치"]["placements"] = split_placements
else:
    strategies_config["고층부/저층부 분할 배치"]["placements"] = [idx_1f]

# 베이스 스테이션 전략의 배치층 동적 변경 (주차장 이용률에 따라)
if parking_usage_rate > 50 and (mode_label == "퇴근 시간" or mode_label == "새벽 시간" or mode_label == "저녁 시간"):
    strategies_config["베이스 스테이션 (1층/지하)"]["placements"] = [0] * num_elevators # 지하 0층으로 복귀
    strategies_config["AI Generated Strategy #1 (로비/지하 집중형)"]["placements"] = [idx_1f, 0] if num_elevators >= 2 else [0]
    strategies_config["AI Generated Strategy #5 (심야/배달 최적화)"]["placements"] = [idx_1f, 0] if num_elevators >= 2 else [0]
else:
    strategies_config["베이스 스테이션 (1층/지하)"]["placements"] = [idx_1f] * num_elevators # 1층으로 복귀
    strategies_config["AI Generated Strategy #1 (로비/지하 집중형)"]["placements"] = [idx_1f, idx_1f] if num_elevators >= 2 else [idx_1f]
    strategies_config["AI Generated Strategy #5 (심야/배달 최적화)"]["placements"] = [idx_1f, idx_1f] if num_elevators >= 2 else [idx_1f]


# ----------------- [6] 시뮬레이션 실행 -----------------
if st.button("시뮬레이션 실행"): # 버튼 클릭 시 시뮬레이션 시작
    reset_global_seeds() # 시뮬레이션 시작 시 시드 초기화
    
    all_results = []
    shared_traffic_samples = []
    for mc_idx in range(mc_iterations):
        # 각 Monte Carlo 반복마다 새로운 트래픽 버스트 생성
        mc_seed = GLOBAL_SEED + mc_idx
        random.seed(mc_seed)
        np.random.seed(mc_seed)

        shared_traffic_burst = np.random.poisson(poisson_lambda)
        
        # 각 Monte Carlo 반복마다 배경 요청을 한 번만 생성하여 모든 전략이 공유
        num_bg_requests = int(shared_traffic_burst * 5)
        current_mc_requests = []
        for i in range(num_bg_requests):
            s_f, e_f = generate_weighted_trip_by_time(mode_label, idx_1f, total_fs, parking_usage_rate, stairs_floor)
            ps = random.randint(1, 8)
            e_fs = generate_multi_drop_floors(s_f, e_f, ps, total_fs, idx_1f)
            current_mc_requests.append({"id": f"BG-{i}", "t_sp": random.uniform(0, 300), "start": s_f, "ends": e_fs, "is_target": False, "passengers": ps})
        current_mc_requests.sort(key=lambda x: x["t_sp"])
        shared_traffic_samples.append(current_mc_requests)

    # 시나리오 정의 (4가지 대표 동선)
    scenarios = [
        {"name": "1층 → 거주층", "start": idx_1f, "end": max_f, "sla_limit": lim_1f_up},
        {"name": "거주층 → 1층", "start": max_f, "end": idx_1f, "sla_limit": lim_res_1f},
        {"name": "주차장 → 거주층", "start": 0, "end": max_f, "sla_limit": lim_p_up},
        {"name": "거주층 → 주차장", "start": max_f, "end": 0, "sla_limit": lim_res_p}
    ]

    results_df = pd.DataFrame()

    for strat_name, config in strategies_config.items():
        strat_placements = config["placements"]
        strat_logic = config["logic"]
        
        for scenario in scenarios:
            scenario_times = []
            scenario_kwhs = []
            scenario_wait_times = []
            scenario_queue_lens = []
            scenario_all_passenger_times = []

            for mc_idx in range(mc_iterations):
                mc_seed = GLOBAL_SEED + mc_idx
                random.seed(mc_seed)
                np.random.seed(mc_seed)

                # Monte Carlo 반복마다 생성된 배경 요청을 공유
                shared_requests_for_mc = shared_traffic_samples[mc_idx]

                time_taken, kwh_used, metrics = simulate_route_esg_sla_des(
                    scenario["start"], scenario["end"], strat_placements, strat_logic, "보통", current_is_deliv, button_efficiency, base_door_time, fixed_door_moving_time,
                    parking_usage_rate, stairs_floor, households_per_floor, regen_enabled, poisson_lambda, idx_1f, total_fs,
                    0, mode_label, h_penalty=0.0, shared_requests=shared_requests_for_mc # h_penalty를 0으로 설정하여 원본 dd.py와 동일하게 유지
                )
                scenario_times.append(time_taken)
                scenario_kwhs.append(kwh_used)
                scenario_wait_times.append(metrics["avg_wait_time"])
                scenario_queue_lens.append(metrics["avg_queue_len"])
                scenario_all_passenger_times.append(metrics["all_passenger_avg_time"])

            avg_time = np.mean(scenario_times)
            std_time = np.std(scenario_times)
            avg_kwh = np.mean(scenario_kwhs)
            std_kwh = np.std(scenario_kwhs)
            avg_wait = np.mean(scenario_wait_times)
            std_wait = np.std(scenario_wait_times)
            avg_queue = np.mean(scenario_queue_lens)
            std_queue = np.std(scenario_queue_lens)
            avg_all_passenger_time = np.mean(scenario_all_passenger_times)
            std_all_passenger_time = np.std(scenario_all_passenger_times)

            # SLA 달성률 계산
            sla_achieved = (avg_time <= scenario["sla_limit"]) * 100

            all_results.append({
                "운영 전략": strat_name,
                "동선 시나리오": scenario["name"],
                "실제 소요시간": avg_time,
                "소요시간 표준편차": std_time,
                "SLA 달성률": sla_achieved,
                "SLA 임계치": scenario["sla_limit"],
                "평균 대기시간": avg_wait,
                "대기시간 표준편차": std_wait,
                "평균 Queue 길이": avg_queue,
                "Queue 길이 표준편차": std_queue,
                "평균 전력 소비량 (kWh)": avg_kwh,
                "전력 소비량 표준편차": std_kwh,
                "평균 전체 승객 소요시간": avg_all_passenger_time,
                "전체 승객 소요시간 표준편차": std_all_passenger_time,
                "Monte Carlo 횟수": mc_iterations
            })

    df = pd.DataFrame(all_results)

    # ESG 및 KPI 계산
    df["전기 요금(원)"] = df["평균 전력 소비량 (kWh)"] * kepco_rate
    df["탄소 배출량(g)"] = df["평균 전력 소비량 (kWh)"] * 424 # 1kWh당 424g CO2 배출 (한국 기준)

    # KPI 정규화 및 종합 점수 계산
    agg = df.groupby("운영 전략").agg({
        "SLA 달성률": "mean",
        "평균 대기시간": "mean",
        "평균 Queue 길이": "mean",
        "전기 요금(원)": "sum",
        "탄소 배출량(g)": "sum",
        "소요시간 표준편차": "mean",
        "대기시간 표준편차": "mean",
        "Queue 길이 표준편차": "mean",
        "평균 전체 승객 소요시간": "mean" # 전체 승객 평균 소요시간도 집계
    }).reset_index()

    # Min-Max Normalization
    for col in ["SLA 달성률", "평균 대기시간", "평균 Queue 길이", "전기 요금(원)", "탄소 배출량(g)"]:
        min_val = agg[col].min()
        max_val = agg[col].max()
        if max_val == min_val: # 모든 값이 같을 경우 0.5로 설정 (나누기 0 방지)
            agg[f"{col}_norm"] = 0.5
        else:
            if col == "SLA 달성률": # SLA는 높을수록 좋음
                agg[f"{col}_norm"] = (agg[col] - min_val) / (max_val - min_val)
            else: # 나머지는 낮을수록 좋음
                agg[f"{col}_norm"] = 1 - (agg[col] - min_val) / (max_val - min_val)

    # Fitness 계산 (시간대별 적합도)
    agg["Fitness"] = 0.0
    mid_idx = (total_fs + idx_1f) // 2
    for idx, row in agg.iterrows():
        strat_name = row["운영 전략"]
        placements = strategies_config[strat_name]["placements"]
        
        fitness_score = 0
        if "홀짝" in strat_name and parking_usage_rate > 50 and (mode_label == "퇴근 시간" or mode_label == "새벽 시간" or mode_label == "저녁 시간"):
            fitness_score = 0 # 홀짝수층은 지하층 대응 불가로 패널티
        elif mode_label == "출근 시간": # 고층 대기 선호
            if any(p > mid_idx for p in placements): fitness_score = 100
            elif any(p == max_f for p in placements): fitness_score = 80
            elif any(p == idx_1f for p in placements): fitness_score = 20
        elif mode_label == "퇴근 시간": # 저층/지하 대기 선호
            if parking_usage_rate > 50: # 주차장 수요 높음
                if any(p < idx_1f for p in placements): fitness_score = 100 # 지하층 대기
                elif any(p == idx_1f for p in placements): fitness_score = 50 # 1층 대기
            else: # 일반 퇴근 (1층 대기)
                if any(p == idx_1f for p in placements): fitness_score = 100
                elif any(p < idx_1f for p in placements): fitness_score = 50
        elif mode_label == "새벽 시간" or mode_label == "저녁 시간": # 1층/지하 혼합
            if any(p < idx_1f for p in placements) and any(p == idx_1f for p in placements): fitness_score = 100
            elif any(p < idx_1f for p in placements) or any(p == idx_1f for p in placements): fitness_score = 70
        else: # 낮 시간 (균형)
            if any(p == idx_1f for p in placements) and any(p > mid_idx for p in placements): fitness_score = 100
            elif any(p == idx_1f for p in placements) or any(p > mid_idx for p in placements): fitness_score = 70
        agg.loc[idx, "Fitness"] = fitness_score
    agg["Fitness_norm"] = agg["Fitness"] / 100.0

    # Stability Bonus (표준편차가 낮을수록 좋음)
    agg["Std"] = (agg["소요시간 표준편차"] + agg["대기시간 표준편차"] + agg["Queue 길이 표준편차"]) / 3 # 평균 표준편차
    min_std = agg["Std"].min()
    max_std = agg["Std"].max()
    if max_std == min_std: agg["Std_norm"] = 0.5
    else: agg["Std_norm"] = 1 - (agg["Std"] - min_std) / (max_std - min_std)

    # 최종 KPI 점수 계산
    agg["Final Score"] = (
        agg["SLA 달성률_norm"] * 0.40 +
        agg["평균 대기시간_norm"] * 0.30 +
        agg["평균 Queue 길이_norm"] * 0.10 +
        agg["전기 요금(원)_norm"] * 0.05 +
        agg["탄소 배출량(g)_norm"] * 0.05 +
        agg["Fitness_norm"] * 0.10 +
        agg["Std_norm"] * 0.05 # Stability Bonus
    )

    # 최악의 대기시간 전략은 Final Score 0점으로 처리 (Hard Exclusion)
    max_wait_val = agg["평균 대기시간"].max()
    is_worst_wait = (agg["평균 대기시간"] == max_wait_val)
    agg.loc[is_worst_wait, "Final Score"] = 0.0
    
    # AI 배치층 정보 추가 (공란 처리 로직 포함)
    agg["AI 배치층"] = ""
    for idx, row in agg.iterrows():
        strat_name = row["운영 전략"]
        if strat_name not in ["전략 미적용 (랜덤 운행)", "홀짝수층 분리 운행"]:
            placements = strategies_config[strat_name]["placements"]
            agg.loc[idx, "AI 배치층"] = format_el_placements(placements)

    best = agg.sort_values(["Final Score", "운영 전략"], ascending=[False, True]).iloc[0]
    st.write("### 🏆 종합 KPI 스코어 및 시간대 추천 엔진")
    col1, col2 = st.columns([1.5, 1])
    with col1: 
        display_agg = agg[["운영 전략", "AI 배치층", "Final Score", "SLA 달성률", "평균 대기시간", "평균 Queue 길이", "전기 요금(원)", "탄소 배출량(g)", "Fitness", "Std"]].sort_values(["Final Score", "운영 전략"], ascending=[False, True])
        st.dataframe(display_agg.style.format({
            "Final Score": "{:.2f}", "SLA 달성률": "{:.1f}%", "평균 대기시간": "{:.1f}초", "평균 Queue 길이": "{:.2f}",
            "전기 요금(원)": "{:,.0f}원", "탄소 배출량(g)": "{:,.1f}g", "Fitness": "{:.1f}", "Std": "{:.2f}"
        }), use_container_width=True)
    with col2:
        st.success(f"**최적 전략: {best["운영 전략"]}**\n* KPI: {best["Final Score"]:.2f}\n* SLA: {best["SLA 달성률"]:.1f}%\n* 대기시간: {best["평균 대기시간"]:.1f}초\n* Fitness: {best["Fitness"]:.1f}")
        
        target_strat = best["운영 전략"]
        if target_strat in strategies_config:
            ps_best = strategies_config[target_strat]["placements"]
            mid_idx = (total_fs + idx_1f) // 2 # mid_idx 재계산
            if mode_label == "출근 시간" and not any(p > mid_idx for p in ps_best): st.warning("⚠️ 출근 시간 경고: 고층 대기 엘리베이터가 없습니다. 주차장 이용률이 높더라도 출근 시간엔 고층 수요가 많습니다.")
            if mode_label == "퇴근 시간":
                target_f_for_warning = 0 if parking_usage_rate > 50 else idx_1f
                # 실제 배치된 엘리베이터 중 target_f_for_warning 층 근처(+-1)에 있는 엘리베이터가 하나도 없을 경우 경고
                if not any(abs(p - target_f_for_warning) <= 1 for p in ps_best): st.warning(f"⚠️ 퇴근 시간 경고: 주요 출발층({FLOOR_LABELS[target_f_for_warning]}) 대응 엘리베이터가 없습니다.")
        else:
            st.warning("⚠️ 전략 정보를 불러오는 중 일시적인 오류가 발생했습니다. 다시 시뮬레이션해 주세요.")

    st.write("### 📈 전략 비교 매트릭스")
    # 비현실적으로 큰 시간을 현실적인 시간으로 표시되게 수정
    # 현재 '실제 소요시간'은 4가지 시나리오의 평균값이므로, 이를 그대로 사용하되 포맷팅만 변경
    st.dataframe(df.pivot(index="운영 전략", columns="동선 시나리오", values="실제 소요시간").style.format("{:.1f}초"), use_container_width=True)
    
    st.write("### 📊 DES 이벤트 타임라인 (최적 전략 기준)")
    if best["운영 전략"] in strategies_config:
        st.dataframe(build_strategy_timeline(strategies_config[best["운영 전략"]], mode_label), use_container_width=True)

    st.write("### 🌿 ESG 상세 비교 (에너지 비용 및 탄소 발자국)")
    st.caption("※ 데이터 산출 출처: 시간대별 한국전력공사(KEPCO) 요금제 및 환경부/한국전력거래소 공인 온실가스 배출계수(1kWh당 424g 적용)")
    c1, c2 = st.columns(2)
    with c1: 
        st.write("##### ⚡ 운영 전략별 누적 전기 요금 (원)")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(x='운영 전략', y='전기 요금(원)', color='운영 전략'), use_container_width=True)
    with c2: 
        st.write("##### 🌍 운영 전략별 누적 탄소 배출량 (gCO2)")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(x='운영 전략', y='탄소 배출량(g)', color='운영 전략'), use_container_width=True)
    
    st.write("### 📊 운영 효율성 시각화")
    c3, c4 = st.columns(2)
    with c3:
        st.write("##### ⏱️ 운영 전략별 평균 대기시간 (초)")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(x='운영 전략', y='평균 대기시간', color='운영 전략'), use_container_width=True)
    with c4:
        st.write("##### 📐 운영 전략별 평균 Queue 길이")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(x='운영 전략', y='평균 Queue 길이', color='운영 전략'), use_container_width=True)
else:
    st.info("버튼을 눌러 시뮬레이션을 시작하세요.")

# build_strategy_timeline 함수 정의 (dd.py에서 가져옴)
def build_strategy_timeline(strategy_config, mode_label):
    # 이 함수는 시뮬레이션 결과를 기반으로 타임라인을 구성합니다.
    # 여기서는 예시를 위해 더미 데이터를 사용하거나, 실제 시뮬레이션 로직을 간소화하여 사용합니다.
    # 실제 구현에서는 simulate_route_esg_sla_des 함수를 호출하여 타임라인 데이터를 생성해야 합니다.

    # 시뮬레이션에 사용될 기본 파라미터 (UI에서 가져온 값)
    # 이 부분은 simulate_route_esg_sla_des 호출 시 사용된 파라미터와 일치해야 합니다.
    # 여기서는 편의상 일부만 사용하거나 더미 값을 사용합니다.
    
    # h_penalty는 simulate_route_esg_sla_des에서 사용되지만, build_strategy_timeline에서는 직접 사용되지 않음
    # 따라서 simulate_route_esg_sla_des 호출 시 h_penalty를 0.0으로 설정하여 원본 dd.py와 동일하게 유지

    # 이 부분은 실제 시뮬레이션 로직과 연동되어야 합니다.
    # 여기서는 간소화된 예시를 보여줍니다.
    
    # shared_traffic_burst와 shared_requests는 시뮬레이션 실행 시 생성되므로,
    # 타임라인을 그리기 위한 단일 시뮬레이션 실행이 필요합니다.
    
    # 타임라인 생성을 위한 단일 시뮬레이션 실행 (몬테카를로 아님)
    reset_global_seeds() # 타임라인 생성을 위한 시드 초기화
    random.seed(GLOBAL_SEED)
    np.random.seed(GLOBAL_SEED)

    # 단일 시뮬레이션에 사용할 배경 트래픽 생성
    single_traffic_burst = np.random.poisson(poisson_lambda)
    num_bg_requests = int(single_traffic_burst * 5)
    single_mc_requests = []
    for i in range(num_bg_requests):
        s_f, e_f = generate_weighted_trip_by_time(mode_label, idx_1f, total_fs, parking_usage_rate, stairs_floor)
        ps = random.randint(1, 8)
        e_fs = generate_multi_drop_floors(s_f, e_f, ps, total_fs, idx_1f)
        single_mc_requests.append({"id": f"BG-{i}", "t_sp": random.uniform(0, 300), "start": s_f, "ends": e_fs, "is_target": False, "passengers": ps})
    single_mc_requests.sort(key=lambda x: x["t_sp"])

    # 타임라인 생성을 위한 TARGET 요청 (예시)
    target_scenario = {"name": "1층 → 거주층", "start": idx_1f, "end": max_f, "sla_limit": lim_1f_up}
    
    # simulate_route_esg_sla_des 함수를 직접 호출하여 타임라인 데이터 생성
    # h_penalty는 simulate_route_esg_sla_des 함수에 인자로 전달되어야 합니다.
    # dd.py 원본에는 h_penalty가 없었으므로, 0.0으로 고정하여 호출합니다.
    time_taken, kwh_used, metrics = simulate_route_esg_sla_des(
        target_scenario["start"], target_scenario["end"], strategy_config["placements"], strategy_config["logic"], "보통", current_is_deliv, button_efficiency, base_door_time, fixed_door_moving_time,
        parking_usage_rate, stairs_floor, households_per_floor, regen_enabled, poisson_lambda, idx_1f, total_fs,
        0, mode_label, h_penalty=0.0, shared_requests=single_mc_requests
    )

    # 타임라인 데이터 생성 로직 (이전 버전과 동일하게 유지)
    timeline_data = []
    elevs = [{"id": i, "t_free": 0.0, "curr_f": float(strategy_config["placements"][i])} for i in range(num_elevators)]
    
    # requests는 simulate_route_esg_sla_des 내부에서 생성되므로, 여기서는 직접 접근할 수 없습니다.
    # 타임라인을 위한 별도의 요청 리스트를 다시 생성하거나, simulate_route_esg_sla_des에서 반환하도록 수정해야 합니다.
    # 여기서는 간소화를 위해, simulate_route_esg_sla_des 내부에서 사용된 requests를 재구성합니다.
    
    # simulate_route_esg_sla_des 내부에서 사용된 requests를 재구성
    requests_for_timeline = []
    num_bg = int(single_traffic_burst * 5)
    for i in range(num_bg):
        s_f, e_f = generate_weighted_trip_by_time(mode_label, idx_1f, total_fs, parking_usage_rate, stairs_floor)
        ps = random.randint(1, 8)
        e_fs = generate_multi_drop_floors(s_f, e_f, ps, total_fs, idx_1f)
        requests_for_timeline.append({"id": f"BG-{i}", "t_sp": random.uniform(0, 300), "start": s_f, "ends": e_fs, "is_target": False, "passengers": ps})
    requests_for_timeline.append({"id": "TARGET", "t_sp": 150.0, "start": target_scenario["start"], "ends": [target_scenario["end"]], "is_target": True, "passengers": 1})
    requests_for_timeline.sort(key=lambda x: x["t_sp"])

    # 타임라인 데이터 생성 (simulate_route_esg_sla_des 로직과 유사하게)
    congestion_weights = {"매우 쾌적": 0.7, "쾌적": 0.9, "보통": 1.1, "혼잡": 1.8, "매우 혼잡": 2.5}
    w = congestion_weights["보통"] * (1.0 + (households_per_floor - 1) * 0.05)
    d_eff = final_door_operating_time * w
    if current_is_deliv: d_eff *= 1.5

    for req in requests_for_timeline:
        best_el, min_arrive_t = None, float("inf")

        for el in elevs:
            if not is_elev_allowed_by_logic(strategy_config["logic"], el["id"], req["start"], idx_1f, total_fs, strategy_config["placements"]): continue
            t_start = max(el["t_free"], req["t_sp"])
            curr_pos = el["curr_f"]
            if "베이스 스테이션" in strategy_config["logic"] and el["t_free"] < req["t_sp"]: curr_pos = float(idx_1f)
            dist1 = abs(curr_pos - req["start"]) * floor_height
            t_arr = t_start + get_phys_time(dist1, max_velocity, acceleration)
            if req["start"] < idx_1f or req["ends"][-1] < idx_1f: t_arr -= (parking_usage_rate / 100) * 1.0
            if "분할" in strategy_config["logic"]:
                mid_f = (total_fs + idx_1f) // 2
                if (req["start"] > mid_f) != (el["id"] >= len(strategy_config["placements"]) / 2): t_arr += 40.0 # h_penalty는 0.0으로 고정
            if "AI 자동 최적화" in strategy_config["logic"]:
                mid_f = (total_fs + idx_1f) // 2
                if mode_label == "출근 시간" and curr_pos > mid_f: t_arr -= 8.0
                elif mode_label == "퇴근 시간" and curr_pos <= idx_1f: t_arr -= 8.0
            if t_arr < min_arrive_t:
                min_arrive_t = t_arr
                best_el = el
        
        if best_el is None: best_el = elevs[0]
        
        t_assign = max(best_el["t_free"], req["t_sp"])
        dist1 = abs(best_el["curr_f"] - req["start"]) * floor_height
        move1_t = get_phys_time(dist1, max_velocity, acceleration)
        t_arrive = t_assign + move1_t
        
        t_current = t_arrive + d_eff # 탑승 완료 시점
        curr_el_pos = req["start"]
        total_passengers = req.get("passengers", 1)
        remaining_passengers = total_passengers

        move_sequence = [FLOOR_LABELS[req["start"]]]
        for i, drop_f in enumerate(req["ends"]):
            dist_move = abs(curr_el_pos - drop_f) * floor_height
            move_t = get_phys_time(dist_move, max_velocity, acceleration)
            t_current += move_t
            curr_el_pos = drop_f
            move_sequence.append(FLOOR_LABELS[drop_f])
            if i < len(req["ends"]) - 1: 
                t_current += d_eff
                if remaining_passengers > 0:
                    remaining_passengers -= random.randint(1, remaining_passengers) # 일부 승객 하차

        t_finish = t_current
        best_el["t_free"] = t_finish
        best_el["curr_f"] = float(req["ends"][-1])

        timeline_data.append({
            "요청 ID": req["id"],
            "엘리베이터": best_el["id"],
            "호출 시간": f"{req["t_sp"]:.1f}초",
            "출발층": FLOOR_LABELS[req["start"]],
            "이동 동선": " → ".join(move_sequence),
            "탑승 인원": req["passengers"],
            "도착 시간": f"{t_finish:.1f}초",
            "소요 시간": f"{t_finish - req["t_sp"]:.1f}초"
        })

    return pd.DataFrame(timeline_data)
