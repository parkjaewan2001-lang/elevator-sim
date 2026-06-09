import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from dataclasses import dataclass
import random
import scipy.stats as stats
from copy import deepcopy

# ----------------- [1] UI 및 페이지 전역 설정 -----------------
st.set_page_config(page_title="Elevator ESG & SLA Lab", layout="wide")
st.title("🏢 Elevator Strategic, ESG & SLA Experiment Lab (Advanced AI Version)")
st.subheader("⚡ 동선별 타임라인·SLA 달성률 및 회생제동 기반 에너지/탄소 통합 추적 시스템")

st.markdown("""
> 💡 **Simulation Methodology (연구 방법론):**
> * **개별 동선 추적:** 4개 동선(1층↔거주층, 주차장↔거주층)의 실시간 소요 시간과 개별 SLA 달성률을 정밀 모니터링합니다.
> * **DES Event-Driven 구조:** 승객 호출 대기열(Queue)이 쌓이면 엘리베이터가 `호출 → 배정 → 출발층 도착 → 탑승 → 목적지 하차`의 이벤트를 순차적으로 처리합니다.
> * **시간대별 수요 가중치:** 출근 시간은 `주거층 → 1층/B1`, 퇴근 시간은 `1층/B1 → 주거층` 호출이 높은 확률로 발생하도록 반영합니다.
> * **Queue 지표 추가:** 모든 운영 전략별로 평균 대기시간, 최대 대기시간, 평균 Queue 길이를 산출합니다.
> * **표준 물리 참조 및 회생제동 모델:** 기어리스 동기모터(Efficiency 85%) 및 KEPCO 요금제 기준.
> * **[NEW] 몬테카를로 시뮬레이션 & 통계 분석:** 각 전략에 대해 지정된 N회 반복 시뮬레이션을 수행하여, 평균, 표준편차, 95% 신뢰구간 및 P90/P95/P99 지표를 산출합니다.
> * **[NEW] 종합 KPI 스코어링:** $Score = 0.4 \times SLA + 0.3 \times \Delta Wait + 0.2 \times \Delta Queue + 0.1 \times \Delta ESG$를 통해 전략 순위를 평가합니다.
> * **[NEW] 휴리스틱 AI 전략 탐색:** 500개의 무작위 배치 조합 중 예상 대기 거리가 가장 짧은 상위 5개를 자동 선별하여 기존 전략과 대조합니다.
""")

# ----------------- [2] SIDEBAR: 설정 변수 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 설정")
    c1, c2 = st.columns(2)

    with c1:
        max_f = st.number_input("지상 최고층", value=30, step=1)

    with c2:
        min_f = st.number_input("지하 최저층", value=5, step=1)

    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10)
    households_per_floor = st.number_input("층당 세대수 (가구)", value=4, min_value=1)
    stairs_floor = st.number_input("계단 이용 권장 층수", value=3, min_value=0, max_value=max_f)
    parking_usage_rate = st.number_input("🚗 주차장 이용 비율 (%)", value=30, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("📊 통계적 트래픽 및 층별 가중치")
    poisson_lambda = st.number_input(
        "포아송 분포 λ (분당 호출 집중도)",
        min_value=1.0, max_value=20.0, value=7.5, step=0.5,
        help="값이 높을수록 앞선 호출이 밀려 대기 시간이 늘어나는 병목 현상이 강해집니다."
    )

    high_floor_penalty = st.number_input(
        "고층부 대기 패널티 계수",
        min_value=1.0, max_value=3.0, value=1.5, step=0.1,
        help="고층일수록 엘리베이터를 놓쳤을 때 발생하는 체감 대기시간 증가율입니다."
    )

    st.divider()
    st.header("🌱 ESG 하드웨어 옵션")
    regen_enabled = st.toggle(
        "🔄 회생제동(Regen) 인버터 활성화", value=True,
        help="끄면 회생전력이 발전되지 않고 열로 방출되는 구축 아파트 상태가 됩니다."
    )

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
    st.header("🔬 연구용 몬테카를로 & 탐색 설정")
    mc_iterations = st.number_input("몬테카를로 반복 횟수 (N)", min_value=1, max_value=1000, value=100, step=10)
    auto_gen_count = st.number_input("AI 무작위 조합 탐색 수", min_value=10, max_value=2000, value=500, step=50)


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

    if "경부하" in mode_selection:
        kepco_rate = 78.0
    elif "중부하" in mode_selection:
        kepco_rate = 132.0
    else:
        kepco_rate = 195.0

with c_custom:
    st.write("##### ✍️ 사용자 수동 배치 설정")
    m_cols = st.columns(num_elevators)
    manual_placements = []

    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(
                f"EL {chr(65 + i)}",
                options=range(total_fs),
                format_func=lambda x: FLOOR_LABELS[x],
                index=idx_1f,
                key=f"v_percent_metrics_{i}"
            )
            manual_placements.append(val)

st.divider()

# ----------------- [4] 공통 함수 -----------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0.0
    d_accel = (v_max ** 2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def generate_weighted_trip_by_time(mode_label, start_idx, tot_floors, parking_rate, stairs_floor):
    residential_min = min(tot_floors - 1, start_idx + stairs_floor + 1)
    residential_floors = list(range(residential_min, tot_floors))
    if not residential_floors: residential_floors = list(range(start_idx + 1, tot_floors))
    if not residential_floors: residential_floors = [start_idx]

    parking_floor = 0
    lobby_floor = start_idx

    def pick_residential_floor(): return int(random.choice(residential_floors))
    def pick_lobby_or_parking(): return parking_floor if random.random() < parking_rate / 100 else lobby_floor

    if mode_label == "출근 시간":
        if random.random() < 0.80:
            start, end = pick_residential_floor(), pick_lobby_or_parking()
        else:
            start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)
    elif mode_label == "퇴근 시간":
        if random.random() < 0.80:
            start, end = pick_lobby_or_parking(), pick_residential_floor()
        else:
            start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)
    elif mode_label == "새벽 시간":
        if random.random() < 0.60:
            start, end = pick_lobby_or_parking(), pick_residential_floor()
        else:
            start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)
    elif mode_label == "저녁 시간":
        if random.random() < 0.50:
            start, end = pick_lobby_or_parking(), pick_residential_floor()
        else:
            start, end = pick_residential_floor(), pick_lobby_or_parking()
    else:
        start, end = random.randint(0, tot_floors - 1), random.randint(0, tot_floors - 1)

    if start == end:
        end = pick_residential_floor() if start == lobby_floor else lobby_floor
    return start, end

def format_placements(placements):
    return ", ".join([FLOOR_LABELS[p] for p in placements])

def format_el_placements(placements):
    return ", ".join([f"EL {chr(65 + i)}:{FLOOR_LABELS[p]}" for i, p in enumerate(placements)])

def is_elev_allowed_by_logic(logic, elev_idx, req_start, start_idx, tot_floors, placements):
    if "홀짝" in logic:
        if req_start > start_idx: return ((req_start - start_idx) % 2 != 0) == (elev_idx % 2 != 0)
    elif "분할" in logic:
        mid = (tot_floors + start_idx) // 2
        if req_start > start_idx: return (req_start > mid) == (elev_idx >= len(placements) / 2)
    return True

@dataclass
class EventRequest:
    req_id: int; t_spawn: float; start_floor: int; end_floor: int; passengers: int = 1
    t_assign: float = 0.0; t_arrive: float = 0.0; t_board: float = 0.0; t_drop: float = 0.0; assigned_el: str = ""

@dataclass
class ElevatorAgent:
    id_name: str; current_floor: float; t_free: float = 0.0

def simulate_route_esg_sla_des(
    target_start, target_end, placements, logic, cong, is_deliv, eff, base_t, fixed_t, 
    p_rate, s_floor, households, is_regen_on, p_lambda, h_penalty, start_idx, tot_floors, shared_traffic_burst, mode_label
):
    if abs(target_start - target_end) <= s_floor and target_start >= start_idx:
        return 5.0, 0.001, {"avg_wait_time": 0.0, "max_wait_time": 0.0, "avg_queue_len": 0.0}

    pure_dwell = max(0.0, base_t - fixed_t)
    door_eff_t = fixed_t + (pure_dwell * (1 - (eff / 100)))

    num_bg = int(shared_traffic_burst * 5)
    requests = []

    for i in range(num_bg):
        s_f, e_f = generate_weighted_trip_by_time(mode_label, start_idx, tot_floors, p_rate, s_floor)
        requests.append({"id": f"BG-{i}", "t_sp": random.uniform(0, 300), "start": s_f, "end": e_f, "is_target": False})

    requests.append({"id": "TARGET", "t_sp": 150.0, "start": target_start, "end": target_end, "is_target": True})
    requests.sort(key=lambda x: x["t_sp"])

    elevs = [{"id": i, "t_free": 0.0, "curr_f": float(placements[i])} for i in range(len(placements))]
    congestion_weights = {"매우 쾌적": 0.7, "쾌적": 0.9, "보통": 1.1, "혼잡": 1.8, "매우 혼잡": 2.5}
    w = congestion_weights[cong] * (1.0 + (households - 1) * 0.05)
    d_eff = door_eff_t * w
    if is_deliv: d_eff *= 1.5

    target_time, target_kwh = 0.0, 0.0
    wait_times, queue_lengths, active_finish_times = [], [], []

    for req in requests:
        active_finish_times = [t for t in active_finish_times if t > req["t_sp"]]
        queue_lengths.append(len(active_finish_times))

        best_el, min_arrive_t = None, float("inf")
        for el in elevs:
            if not is_elev_allowed_by_logic(logic, el["id"], req["start"], start_idx, tot_floors, placements): continue
            t_start = max(el["t_free"], req["t_sp"])
            dist1 = abs(start_idx - req["start"]) * floor_height if logic == "베이스 스테이션 집중" and el["t_free"] <= req["t_sp"] else abs(el["curr_f"] - req["start"]) * floor_height
            t_arr = t_start + get_phys_time(dist1, max_velocity, acceleration)
            if req["start"] > start_idx: t_arr += (req["start"] - start_idx) * h_penalty * 0.2
            if req["start"] < start_idx or req["end"] < start_idx: t_arr -= (p_rate / 100) * 1.0

            if t_arr < min_arrive_t:
                min_arrive_t = t_arr
                best_el = el

        if best_el is None: best_el = elevs[0]

        t_assign = max(best_el["t_free"], req["t_sp"])
        dist1 = abs(start_idx - req["start"]) * floor_height if logic == "베이스 스테이션 집중" and best_el["t_free"] <= req["t_sp"] else abs(best_el["curr_f"] - req["start"]) * floor_height
        move1_t = get_phys_time(dist1, max_velocity, acceleration)
        t_arrive = t_assign + move1_t
        wait_time = max(0.0, t_arrive - req["t_sp"])
        wait_times.append(wait_time)

        t_board = t_arrive + d_eff
        move2_t = get_phys_time(abs(req["start"] - req["end"]) * floor_height, max_velocity, acceleration)
        t_drop = t_board + move2_t
        t_finish = t_drop + d_eff

        start_before_update = best_el["curr_f"]
        best_el["curr_f"] = float(req["end"])
        best_el["t_free"] = t_finish
        active_finish_times.append(t_finish)

        if req["is_target"]:
            target_time = t_finish - req["t_sp"]
            e_m1, e_m2 = ((500 * 9.8 * max_velocity * move1_t) / (0.85 * 3600 * 1000)), ((500 * 9.8 * max_velocity * move2_t) / (0.85 * 3600 * 1000))
            if is_deliv: e_m1 *= 2.4; e_m2 *= 2.4
            rf1, rf2 = 1.05, 1.05

            if is_regen_on:
                rf1 = -0.35 if req["start"] > start_before_update else 1.05
                is_up2, is_heavy = req["end"] > req["start"], (w >= 1.2 or is_deliv)
                if is_up2 and not is_heavy: rf2 = -0.35
                elif not is_up2 and is_heavy: rf2 = -0.40
                elif is_up2 and is_heavy: rf2 = 1.30
                else: rf2 = 1.0
            else:
                if (req["end"] > req["start"]) and (w >= 1.2 or is_deliv): rf2 = 1.30

            target_kwh = (e_m1 * rf1) + (e_m2 * rf2) + (0.001 * w * (1.8 if is_deliv else 1.0))

    queue_metrics = {
        "avg_wait_time": float(np.mean(wait_times)) if wait_times else 0.0,
        "max_wait_time": float(np.max(wait_times)) if wait_times else 0.0,
        "avg_queue_len": float(np.mean(queue_lengths)) if queue_lengths else 0.0
    }
    return target_time, target_kwh, queue_metrics

def build_strategy_timeline(config, saved_mode_label):
    random.seed(1000)
    demo_queue = []
    for i in range(8):
        start, end = generate_weighted_trip_by_time(saved_mode_label, idx_1f, total_fs, parking_usage_rate, stairs_floor)
        demo_queue.append(EventRequest(i + 1, random.uniform(0, 90), start, end, random.randint(1, 10)))
    
    demo_queue.sort(key=lambda x: x.t_spawn)
    el_agents = [ElevatorAgent(f"EL-{chr(65 + i)}", float(config["placements"][i])) for i in range(num_elevators)]

    for req in demo_queue:
        best_el, min_arrive_t = None, float("inf")
        for el_idx, el in enumerate(el_agents):
            if not is_elev_allowed_by_logic(config["logic"], el_idx, req.start_floor, idx_1f, total_fs, config["placements"]): continue
            t_start = max(el.t_free, req.t_spawn)
            dist_to_req = abs(idx_1f - req.start_floor) * floor_height if config["logic"] == "베이스 스테이션 집중" and el.t_free <= req.t_spawn else abs(el.current_floor - req.start_floor) * floor_height
            t_arr = t_start + get_phys_time(dist_to_req, max_velocity, acceleration)
            if t_arr < min_arrive_t:
                min_arrive_t = t_arr
                best_el = el

        if best_el is None: best_el = el_agents[0]

        req.assigned_el = best_el.id_name
        req.t_assign = max(best_el.t_free, req.t_spawn)
        dist1 = abs(idx_1f - req.start_floor) * floor_height if config["logic"] == "베이스 스테이션 집중" and best_el.t_free <= req.t_spawn else abs(best_el.current_floor - req.start_floor) * floor_height
        req.t_arrive = req.t_assign + get_phys_time(dist1, max_velocity, acceleration)
        req.t_board = req.t_arrive + final_door_operating_time
        req.t_drop = req.t_board + get_phys_time(abs(req.start_floor - req.end_floor) * floor_height, max_velocity, acceleration)

        best_el.t_free = req.t_drop + final_door_operating_time
        best_el.current_floor = req.end_floor

    base_dt = pd.Timestamp("2026-06-07 08:00:00")
    def fmt(s): return (base_dt + pd.Timedelta(seconds=int(s))).strftime("%H:%M:%S")

    timeline_rows = []
    for req in demo_queue:
        timeline_rows.append({
            "호출 ID": f"REQ-{req.req_id}", "이동 동선": f"{FLOOR_LABELS[req.start_floor]} → {FLOOR_LABELS[req.end_floor]}",
            "배정 E/V": req.assigned_el, "1. 호출 발생": fmt(req.t_spawn), "2. E/V 배정": fmt(req.t_assign),
            "3. 도착(문열림)": fmt(req.t_arrive), "4. 탑승 완료": fmt(req.t_board), "5. 목적지 하차": fmt(req.t_drop),
            "대기시간": f"{req.t_arrive - req.t_spawn:.1f}초"
        })
    return pd.DataFrame(timeline_rows)


# ----------------- [NEW] 수요 히트맵 프로파일 생성기 -----------------
def generate_demand_profile(m_label, samples=5000):
    start_counts = np.zeros(total_fs)
    heatmap_data = []
    for _ in range(samples):
        s, e = generate_weighted_trip_by_time(m_label, idx_1f, total_fs, parking_usage_rate, stairs_floor)
        start_counts[s] += 1
        heatmap_data.append({"Start Floor": FLOOR_LABELS[s], "End Floor": FLOOR_LABELS[e]})
    return start_counts, pd.DataFrame(heatmap_data)


# ----------------- 운영 전략 대기 포지션 맵 빌드 -----------------
strategies_config = {}
np.random.seed(42)

strategies_config["전략 미적용 (랜덤 운행)"] = {"placements": list(np.random.randint(0, total_fs, num_elevators)), "logic": "자유 운행", "desc": "무작위 방치 상태"}

oe_placements = [int(np.random.choice([f for f in range(total_fs) if f <= idx_1f or (f - idx_1f) % 2 != 0])) if i % 2 == 0 else int(np.random.choice([f for f in range(total_fs) if f <= idx_1f or (f - idx_1f) % 2 == 0])) for i in range(num_elevators)] if num_elevators > 1 else [int(np.random.randint(0, total_fs))]
strategies_config["홀짝수층 분리 운행"] = {"placements": oe_placements, "logic": "홀짝 운행", "desc": "홀/짝수층 전담 정차로 감속 손실 방지"}

mid_idx = (total_fs + idx_1f) // 2
split_placements = [int(idx_1f + (mid_idx - idx_1f) / 2) if i < num_elevators / 2 else int(mid_idx + (total_fs - mid_idx) / 2) for i in range(num_elevators)] if num_elevators > 1 else [mid_idx]
strategies_config["고층부/저층부 분할배치"] = {"placements": split_placements, "logic": "분할 배치", "desc": "건물 상/하방 구역 분할 대기"}

strategies_config["베이스 스테이션 집중"] = {"placements": [idx_1f] * num_elevators, "logic": "베이스 스테이션 집중", "desc": "운행 종료 후 무조건 1층 로비 복귀"}

spacing_placements = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)] if num_elevators > 1 else [mid_idx]
strategies_config["동적 간격 배치"] = {"placements": spacing_placements, "logic": "자유 운행", "desc": "전체 가용 층수에 등간격 분산 대기"}

# [NEW] 수요예측 기반 AI 자동 최적화 배치 도출
demand_counts, df_heatmap = generate_demand_profile(mode_label)
top_demand_floors = np.argsort(demand_counts)[-num_elevators:]
advanced_ai_pos = sorted([int(f) for f in top_demand_floors])

strategies_config["AI 자동 최적화"] = {
    "placements": advanced_ai_pos,
    "logic": "자유 운행",
    "desc": f"예상 수요 히트맵 기반 지능형 밀집 구역 배치 ({mode_label})"
}

strategies_config["사용자 수동 배치"] = {"placements": manual_placements, "logic": "자유 운행", "desc": "연구원 임의 정의 슬롯 배치"}

# [NEW] AI Strategy Auto-Generation (Heuristic Search)
st.sidebar.markdown("---")
st.sidebar.info("💡 **수요 히트맵 생성 완료.** AI 무작위 탐색 알고리즘을 준비합니다.")

# ----------------- UI 렌더링 -----------------
st.subheader("🔥 [수요예측] 시간대별 예상 호출 빈도 히트맵")
st.write(f"현재 선택된 시간대: **{mode_label}** 기준, {len(df_heatmap)}건의 샘플링을 통해 예상되는 층별 출발-도착 밀집도를 분석합니다.")

heatmap_chart = alt.Chart(df_heatmap).mark_rect().encode(
    x=alt.X('End Floor:N', title='목적지 층 (End Floor)', sort=FLOOR_LABELS),
    y=alt.Y('Start Floor:N', title='출발 층 (Start Floor)', sort=FLOOR_LABELS[::-1]),
    color=alt.Color('count()', scale=alt.Scale(scheme='viridis'), title='호출 빈도')
).properties(width='container', height=400)
st.altair_chart(heatmap_chart, use_container_width=True)


st.subheader("🌐 통합 DES & Monte Carlo 환경 가동")
c_env1, c_env2 = st.columns(2)
with c_env1: congestion = st.radio("건물 내부 혼잡도 세부 선택", options=["매우 쾌적", "쾌적", "보통", "혼잡", "매우 혼잡"], index=2, horizontal=True)
with c_env2: delivery_mode = st.toggle("📦 배달 패널티 활성화", value=current_is_deliv)

infra_badge = "🟢 회생제동 인버터 활성화 모드 (신축형)" if regen_enabled else "🔴 회생제동 인버터 비활성화 모드 (구축형)"
st.info(f"현재 물리 엔진 타겟 상태: **{infra_badge}** | 몬테카를로 반복수: **{mc_iterations}회**")

if "strategy_results" not in st.session_state: st.session_state.strategy_results = None

if st.button("🚀 N회 반복 시뮬레이션 및 종합 KPI 탐색 산출", type="primary", use_container_width=True):
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # --- [NEW] Heuristic Auto-Search ---
    status_text.text(f"🔍 {auto_gen_count}개의 무작위 배치 조합 탐색 중...")
    random_placements = list(set([tuple(sorted(np.random.randint(0, total_fs, num_elevators))) for _ in range(auto_gen_count)]))
    scores = []
    for p in random_placements:
        # Expected Wait Time Proxy: sum of demand density * distance to nearest elevator
        score = sum((demand_counts[f] / 5000) * min([abs(f - ep) for ep in p]) for f in range(total_fs))
        scores.append((score, p))
    scores.sort(key=lambda x: x[0])
    
    for idx, (sc, p) in enumerate(scores[:5]):
        strategies_config[f"AI Generated Strategy #{idx+1}"] = {
            "placements": list(p), "logic": "자유 운행", "desc": "휴리스틱 알고리즘 탐색 상위 조합"
        }

    # --- [NEW] Monte Carlo Setup ---
    avg_res_f = int(idx_1f + (max_f - 1) * 0.7)
    scenarios = {
        "1층 ⬆️ 거주층": (idx_1f, avg_res_f, lim_1f_up),
        "거주층 ⬇️ 1층": (avg_res_f, idx_1f, lim_res_1f),
        "주차장 ⬆️ 거주층": (0, avg_res_f, lim_p_up),
        "거주층 ⬇️ 주차장": (avg_res_f, 0, lim_res_p)
    }

    # Fair MC Seeds
    mc_seeds = [random.randint(0, 999999) for _ in range(mc_iterations)]
    
    # Result Storage
    raw_stats = []
    mean_matrix_results = []
    total_steps = len(scenarios) * len(strategies_config) * mc_iterations
    current_step = 0

    for s_name, (start, end, target_sla) in scenarios.items():
        for strat_name, config in strategies_config.items():
            
            eff_param = button_efficiency if strat_name != "전략 미적용 (랜덤 운행)" else 0
            p_rate_param = parking_usage_rate if strat_name != "전략 미적용 (랜덤 운행)" else 0
            s_floor_param = stairs_floor if strat_name != "전략 미적용 (랜덤 운행)" else 0
            
            mc_times, mc_kwhs, mc_waits, mc_q_lens, mc_slas = [], [], [], [], []
            
            for it in range(mc_iterations):
                np.random.seed(mc_seeds[it])
                random.seed(mc_seeds[it])
                shared_traffic_burst = np.random.poisson(poisson_lambda)
                
                calc_time, calc_kwh, queue_metrics = simulate_route_esg_sla_des(
                    start, end, config["placements"], config["logic"], congestion, delivery_mode,
                    eff_param, base_door_time, fixed_door_moving_time, p_rate_param, s_floor_param, 
                    households_per_floor, regen_enabled, poisson_lambda, high_floor_penalty, idx_1f, total_fs, shared_traffic_burst, mode_label
                )
                
                mc_times.append(calc_time)
                mc_kwhs.append(calc_kwh)
                mc_waits.append(queue_metrics["avg_wait_time"])
                mc_q_lens.append(queue_metrics["avg_queue_len"])
                mc_slas.append(100.0 if calc_time <= target_sla else (target_sla / calc_time) * 100)
                
                current_step += 1
                if current_step % 50 == 0:
                    progress_bar.progress(current_step / total_steps)
                    status_text.text(f"🔄 몬테카를로 시뮬레이션 연산 중... ({current_step}/{total_steps})")

            # Statistics
            mean_time = np.mean(mc_times)
            mean_wait = np.mean(mc_waits)
            mean_q_len = np.mean(mc_q_lens)
            mean_kwh = np.mean(mc_kwhs)
            mean_sla = np.mean(mc_slas)
            
            calc_cost = mean_kwh * kepco_rate
            calc_carbon = mean_kwh * 424.0
            sla_excess = max(0.0, mean_time - target_sla)
            
            placement_text = "-" if strat_name in ["전략 미적용 (랜덤 운행)", "홀짝수층 분리 운행"] else format_el_placements(config["placements"])

            mean_matrix_results.append({
                "운영 전략": strat_name, "AI 배치층": placement_text, "동선 시나리오": s_name,
                "실제 소요시간": mean_time, "평균 대기시간": mean_wait, "최대 대기시간": np.max(mc_waits),
                "평균 Queue 길이": mean_q_len, "목표 SLA": target_sla, "SLA 초과(초)": sla_excess,
                "SLA 달성률": mean_sla, "전력 소비량(kWh)": mean_kwh, "전기 요금(원)": calc_cost, "탄소 배출량(g)": calc_carbon
            })
            
            raw_stats.append({
                "운영 전략": strat_name, "시나리오": s_name,
                "Mean_Wait": mean_wait, "STD_Wait": np.std(mc_waits), 
                "CI95_Wait": 1.96 * np.std(mc_waits) / np.sqrt(mc_iterations),
                "Min_Wait": np.min(mc_waits), "Max_Wait": np.max(mc_waits),
                "P90_Wait": np.percentile(mc_waits, 90), "P95_Wait": np.percentile(mc_waits, 95), "P99_Wait": np.percentile(mc_waits, 99)
            })

    progress_bar.empty()
    status_text.empty()

    st.session_state.strategy_results = {
        "df_matrix": pd.DataFrame(mean_matrix_results),
        "df_stats": pd.DataFrame(raw_stats),
        "mode_label": mode_label,
        "strategies_config": strategies_config,
        "regen_enabled": regen_enabled
    }

if st.session_state.strategy_results is not None:
    df_matrix = st.session_state.strategy_results["df_matrix"]
    df_stats = st.session_state.strategy_results["df_stats"]
    saved_mode_label = st.session_state.strategy_results["mode_label"]
    saved_strategies_config = st.session_state.strategy_results["strategies_config"]
    saved_regen_enabled = st.session_state.strategy_results["regen_enabled"]

    # ----------------- [NEW] KPI Scoring & Ranking -----------------
    # Aggregate across scenarios to get one master row per strategy
    strat_agg = df_matrix.groupby("운영 전략").agg({
        "SLA 달성률": "mean", "평균 대기시간": "mean", "평균 Queue 길이": "mean", "전력 소비량(kWh)": "sum"
    }).reset_index()

    base_row = strat_agg[strat_agg["운영 전략"] == "전략 미적용 (랜덤 운행)"].iloc[0]
    
    kpi_results = []
    for _, row in strat_agg.iterrows():
        strat = row["운영 전략"]
        sla = row["SLA 달성률"]
        wait_imp = (base_row["평균 대기시간"] - row["평균 대기시간"]) / base_row["평균 대기시간"] * 100 if base_row["평균 대기시간"] > 0 else 0
        q_imp = (base_row["평균 Queue 길이"] - row["평균 Queue 길이"]) / base_row["평균 Queue 길이"] * 100 if base_row["평균 Queue 길이"] > 0 else 0
        esg_imp = (base_row["전력 소비량(kWh)"] - row["전력 소비량(kWh)"]) / base_row["전력 소비량(kWh)"] * 100 if base_row["전력 소비량(kWh)"] > 0 else 0
        
        score = (0.4 * sla) + (0.3 * wait_imp) + (0.2 * q_imp) + (0.1 * esg_imp)
        kpi_results.append({
            "운영 전략": strat, "Final Score": np.clip(score, 0, 100),
            "SLA 평균": sla, "대기시간 개선율(%)": wait_imp, "Queue 개선율(%)": q_imp, "ESG 개선율(%)": esg_imp
        })
        
    df_kpi = pd.DataFrame(kpi_results).sort_values("Final Score", ascending=False).reset_index(drop=True)
    best_strat_name = df_kpi.iloc[0]["운영 전략"]
    best_strat_metrics = df_kpi.iloc[0]

    # --- Section: Recommendation Engine & Conclusion ---
    st.write("### 🏆 종합 KPI 스코어 및 시간대 추천 엔진")
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        st.dataframe(
            df_kpi.style.format({"Final Score": "{:.1f}점", "SLA 평균": "{:.1f}%", "대기시간 개선율(%)": "{:+.1f}%", "Queue 개선율(%)": "{:+.1f}%", "ESG 개선율(%)": "{:+.1f}%"})
            .background_gradient(cmap="Blues", subset=["Final Score"]), 
            use_container_width=True
        )
    
    with col2:
        rec_placement = saved_strategies_config[best_strat_name]['placements']
        if best_strat_name in ["전략 미적용 (랜덤 운행)", "홀짝수층 분리 운행"]:
            rec_pl_text = "유동적 로직에 따름"
        else:
            rec_pl_text = ", ".join([f"EL-{chr(65+i)} = {FLOOR_LABELS[p]}" for i, p in enumerate(rec_placement)])
            
        st.success(f"""
        **💡 {saved_mode_label} 최적화 추천**
        * **최적 전략**: {best_strat_name}
        * **추천 배치**: {rec_pl_text}
        * **예상 SLA**: {best_strat_metrics['SLA 평균']:.1f}%
        * **예상 평균 대기시간**: {strat_agg[strat_agg['운영 전략'] == best_strat_name]['평균 대기시간'].values[0]:.1f}초
        """)

    st.write("### 📝 논문용 결론 자동 생성 (Auto Conclusion)")
    st.info(f"""
    본 시뮬레이션에서는 **{saved_mode_label}** 기준 **{best_strat_name}**이(가) 가장 우수한 성능을 보였다.
    평균 SLA 달성률은 **{best_strat_metrics['SLA 평균']:.1f}%**였으며, 기존 랜덤 운행 대비 평균 대기시간이 **{best_strat_metrics['대기시간 개선율(%)']:.1f}%** 감소하였다.
    또한 Queue 길이는 **{best_strat_metrics['Queue 개선율(%)']:.1f}%** 감소하였고, 전력 소비량은 **{best_strat_metrics['ESG 개선율(%)']:.1f}%** 절감되었다.
    따라서 본 건물에서는 해당 시간대 기준 **{rec_pl_text}** 배치 전략이 가장 효율적인 것으로 분석되었다.
    """)

    st.divider()

    # --- Section: Bottleneck Analysis ---
    st.write("### 🚨 시스템 병목 분석 리포트")
    bottlenecks = []
    base_agg = strat_agg[strat_agg["운영 전략"] == "전략 미적용 (랜덤 운행)"].iloc[0]
    
    if base_agg["평균 Queue 길이"] > 5.0:
        bottlenecks.append("⚠️ **Queue 과도 증가**: 피크타임 발생 빈도가 서비스 처리 속도를 초과하여 대기열이 급증함.")
    
    df_raw_base = df_matrix[df_matrix["운영 전략"] == "전략 미적용 (랜덤 운행)"]
    if df_raw_base["최대 대기시간"].max() > 120:
        bottlenecks.append("⚠️ **엘리베이터 분산 부족**: 최대 대기시간이 120초를 초과하여 특정 동선에 엘리베이터 할당이 지연됨.")
        
    if "출근 시간" in saved_mode_label and demand_counts[idx_1f] / sum(demand_counts) < 0.2:
        bottlenecks.append("⚠️ **고층부 호출 집중**: 고층 주거 구역에서의 집중 하행 호출 발생으로 인한 1층 수송 지연.")
        
    if demand_counts[0] / sum(demand_counts) > 0.3:
        bottlenecks.append("⚠️ **B1 호출 과다**: 주차장층 진출입 비율이 높아 추가적인 할당 알고리즘 조정이 필요함.")

    if not bottlenecks:
        st.success("✅ 심각한 병목 현상이 감지되지 않았습니다. 현재 설정 인프라로 수요 소화가 원활합니다.")
    else:
        for b in bottlenecks:
            st.warning(b)

    st.divider()

    # --- Section: Deep Research Stats ---
    st.write(f"### 🔬 연구용 상세 통계 지표 (몬테카를로 N={mc_iterations}회 반복)")
    with st.expander("통계 데이터 테이블 펼쳐보기"):
        st.dataframe(df_stats.style.format(precision=2), use_container_width=True)

    st.divider()

    # --- Existing Original Sections Below ---
    queue_summary = df_matrix.groupby("운영 전략").agg({
        "평균 대기시간": "mean", "최대 대기시간": "max", "평균 Queue 길이": "mean"
    }).reset_index()

    st.write("### 🧍 [Queue 대기 지표 요약] 전체 전략별 평균·최대 대기시간 및 Queue 길이")
    queue_rows = [{"운영 전략": r["운영 전략"], "평균 대기시간": f"{r['평균 대기시간']:.1f}초", "최대 대기시간": f"{r['최대 대기시간']:.1f}초", "평균 Queue 길이": f"{r['평균 Queue 길이']:.1f}명"} for _, r in queue_summary.iterrows()]
    st.dataframe(pd.DataFrame(queue_rows).set_index("운영 전략"), use_container_width=True)

    st.write("### 📈 [동선별 정밀 스코어보드] 운영 전략 × 시나리오 매트릭스 (% 대조)")
    final_rows = []
    for strat_name in saved_strategies_config.keys():
        strat_df = df_matrix[df_matrix["운영 전략"] == strat_name]
        row_data = {"운영 전략": strat_name, "AI 배치층": strat_df["AI 배치층"].iloc[0]}

        for _, row in strat_df.iterrows():
            scen = row["동선 시나리오"]
            time_v = row["실제 소요시간"]
            pass_v = row["SLA 달성률"]
            excess_v = row["SLA 초과(초)"]

            base_time = df_matrix[(df_matrix["운영 전략"] == "전략 미적용 (랜덤 운행)") & (df_matrix["동선 시나리오"] == scen)]["실제 소요시간"].values[0]
            time_diff_pct = ((time_v - base_time) / base_time) * 100
            pct_str = f"({time_diff_pct:+.1f}%)" if strat_name != "전략 미적용 (랜덤 운행)" else "(기준)"
            status_icon = "⭕" if pass_v >= 100.0 else f"❌ (+{excess_v:.1f}초)"

            row_data[f"{scen} (소요시간)"] = f"{time_v:.1f}초 {pct_str}"
            row_data[f"{scen} (달성률)"] = f"{pass_v:.1f}% ({status_icon})"

        final_rows.append(row_data)

    df_pivot = pd.DataFrame(final_rows).set_index("운영 전략")
    ordered_cols = ["AI 배치층", "1층 ⬆️ 거주층 (소요시간)", "1층 ⬆️ 거주층 (달성률)", "거주층 ⬇️ 1층 (소요시간)", "거주층 ⬇️ 1층 (달성률)", "주차장 ⬆️ 거주층 (소요시간)", "주차장 ⬆️ 거주층 (달성률)", "거주층 ⬇️ 주차장 (소요시간)", "거주층 ⬇️ 주차장 (달성률)"]
    st.dataframe(df_pivot[ordered_cols], use_container_width=True)

    st.divider()

    st.write("### 🚹 DES 이벤트 타임라인 시각화 모니터")
    strategy_options = list(saved_strategies_config.keys())
    best_idx = strategy_options.index(best_strat_name) if best_strat_name in strategy_options else 0

    selected_strategy = st.selectbox("DES 타임라인에 적용할 전략 선택", options=strategy_options, index=best_idx, help="기본값은 종합 KPI 스코어 최고 성능 전략입니다.")
    selected_config = saved_strategies_config[selected_strategy]
    
    selected_placement_text = "-" if selected_strategy in ["전략 미적용 (랜덤 운행)", "홀짝수층 분리 운행"] else format_placements(selected_config["placements"])
    timeline_df = build_strategy_timeline(selected_config, saved_mode_label)

    st.markdown(f"#### DES 이벤트 타임라인<br>(전략: {selected_strategy} / 배치층: {selected_placement_text} / 시간대: {saved_mode_label})", unsafe_allow_html=True)
    st.caption("이 타임라인은 선택한 전략의 실제 초기 엘리베이터 배치 위치와 운행 로직을 반영해 생성됩니다.")
    st.dataframe(timeline_df, use_container_width=True)

    st.divider()

    st.write(f"### 🌿 [ESG 친환경 부하 분석] 전략별 누적 에너지 및 탄소 배출 비교 ({'회생제동 ON' if saved_regen_enabled else '회생제동 OFF'})")
    df_esg_summary = df_matrix.groupby("운영 전략").agg({"전력 소비량(kWh)": "sum", "전기 요금(원)": "sum", "탄소 배출량(g)": "sum"}).reset_index()
    base_row_esg = df_esg_summary[df_esg_summary["운영 전략"] == "전략 미적용 (랜덤 운행)"].iloc[0]

    esg_rows = []
    for _, row in df_esg_summary.iterrows():
        strat, kwh_v, cost_v, co2_v = row["운영 전략"], row["전력 소비량(kWh)"], row["전기 요금(원)"], row["탄소 배출량(g)"]
        kwh_diff_pct = ((kwh_v - base_row_esg["전력 소비량(kWh)"]) / base_row_esg["전력 소비량(kWh)"]) * 100 if base_row_esg["전력 소비량(kWh)"] != 0 else 0
        cost_diff_pct = ((cost_v - base_row_esg["전기 요금(원)"]) / base_row_esg["전기 요금(원)"]) * 100 if base_row_esg["전기 요금(원)"] != 0 else 0
        co2_diff_pct = ((co2_v - base_row_esg["탄소 배출량(g)"]) / base_row_esg["탄소 배출량(g)"]) * 100 if base_row_esg["탄소 배출량(g)"] != 0 else 0

        esg_rows.append({
            "운영 전략": strat,
            "총 전력 소비량": f"{kwh_v:.4f} kWh ({kwh_diff_pct:+.1f}%)" if strat != "전략 미적용 (랜덤 운행)" else f"{kwh_v:.4f} kWh (기준)",
            "총 예상 전기요금": f"{cost_v:.1f} 원 ({cost_diff_pct:+.1f}%)" if strat != "전략 미적용 (랜덤 운행)" else f"{cost_v:.1f} 원 (기준)",
            "누적 탄소 배출 발자국": f"{co2_v:.1f} g CO₂ ({co2_diff_pct:+.1f}%)" if strat != "전략 미적용 (랜덤 운행)" else f"{co2_v:.1f} g CO₂ (기준)"
        })

    st.dataframe(pd.DataFrame(esg_rows).set_index("운영 전략"), use_container_width=True)

    st.divider()

    st.write("### 📊 전략 평가 핵심 데이터 시각화 분석")
    g_col1, g_col2 = st.columns(2)

    with g_col1:
        st.write("##### ⏳ [동선별] 실제 소요 시간 전략별 비교")
        time_chart = alt.Chart(df_matrix).mark_bar().encode(
            x=alt.X("운영 전략:N", axis=alt.Axis(title=None, labels=False)),
            y=alt.Y("실제 소요시간:Q", title="소요 시간 (초)"),
            color=alt.Color("운영 전략:N", legend=alt.Legend(title="운영 전략", orient="bottom")),
            column=alt.Column("동선 시나리오:N", title="시나리오 동선 구간")
        ).properties(width=130, height=300)
        st.altair_chart(time_chart)
        st.caption("💡 각 동선 구역별로 막대가 낮을수록 더 효율적이고 빠른 알고리즘 배치 전략임을 뜻합니다.")

    with g_col2:
        st.write("##### ⚡ [에너지] 전략별 총 전력 소비량(kWh) 대조 그래프")
        energy_chart = alt.Chart(df_esg_summary).mark_bar().encode(
            x=alt.X("운영 전략:N", axis=alt.Axis(labelAngle=-45, title="운영 전략")),
            y=alt.Y("전력 소비량(kWh):Q", title="누적 전력 소비량 (kWh)"),
            color=alt.Color("운영 전략:N", legend=None)
        ).properties(height=345)
        st.altair_chart(energy_chart, use_container_width=True)
        st.caption("💡 무부하 대기 위치 최적화 및 회생 제동으로 자가발전된 에너지가 최종 반영된 총 순 소비량입니다.")

    st.write("##### 🧍 [Queue] 전체 전략별 평균 대기시간 비교")
    queue_chart = alt.Chart(queue_summary).mark_bar().encode(
        x=alt.X("운영 전략:N", axis=alt.Axis(labelAngle=-45, title="운영 전략")),
        y=alt.Y("평균 대기시간:Q", title="평균 대기시간 (초)"),
        color=alt.Color("운영 전략:N", legend=None),
        tooltip=["운영 전략", "평균 대기시간", "최대 대기시간", "평균 Queue 길이"]
    ).properties(height=330)
    st.altair_chart(queue_chart, use_container_width=True)

else:
    st.header("🚹 DES 이벤트 타임라인 시각화 모니터")
    st.info("먼저 `N회 반복 시뮬레이션 및 종합 KPI 탐색 산출` 버튼을 눌러 전략 비교 결과를 생성하면, 최고 성능 전략 또는 선택 전략 기준의 DES 이벤트 타임라인이 표시됩니다.")
