import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] 전역 페이지 설정 및 소개 -----------------
st.set_page_config(page_title="엘리베이터 ESG & SLA 랩", layout="wide")
st.title("🏢 엘리베이터 종합 운영 전략 및 ESG·SLA 실증 실험실")

st.markdown("""
> 💡 **시뮬레이션 분석 방법론:**
> * **4대 핵심 동선 추적:** 가장 빈번한 4가지 이동 경로의 실시간 소요 시간과 SLA(서비스 수준 계약) 달성률을 계산합니다.
> * **회생제동 인버터 가변 대조:** 신축 아파트(🔄 회생제동 ON)와 구축 아파트(🔥 저항제동 방열)의 하드웨어 차이에 따른 전력 제어 효율을 모니터링합니다.
> * **전략별 상대 대조:** 모든 지표는 기준점인 **'전략 미적용 (랜덤 운행)'** 대비 증감률(%)로 자동 환산됩니다.
""")

# ----------------- [2] 사이드바: 기본 제원 설정 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 제원")
    col_f1, col_f2 = st.columns(2)
    with col_f1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with col_f2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    num_elevators = st.number_input("엘리베이터 대수", value=2, min_value=1, max_value=10)
    households_per_floor = st.number_input("층당 세대수 (가구)", value=4, min_value=1)
    stairs_floor = st.number_input("계단 이용 권장 층수", value=3, min_value=0, max_value=max_f)
    parking_usage_rate = st.number_input("🚗 주차장 이용 비율 (%)", value=30, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("🌱 ESG 하드웨어 옵션")
    regen_enabled = st.toggle("🔄 회생제동 인버터 활성화", value=True, help="끄면 회생 전력을 회수하지 못하고 열로 버리는 구축 상태가 됩니다.")

    st.divider()
    st.header("🚀 물리 엔진 세부 튜닝")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)
    
    fixed_door_moving_time = st.number_input("문 개폐 기계 작동 시간 (초)", value=4.0, min_value=1.0, step=0.5)
    base_door_time = st.number_input("기본 전체 문 대기 시간 (초)", value=7.0, min_value=fixed_door_moving_time + 0.5, step=0.5)
    button_efficiency = st.number_input("🔘 닫힘 버튼 이용 효율 (%)", value=40, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("⚠️ 서비스 제한 시간 (SLA) 설정")
    lim_1f_up = st.number_input("목표: 1층 → 거주층 (초)", value=45, min_value=10)
    lim_res_1f = st.number_input("목표: 거주층 → 1층 (초)", value=55, min_value=10)
    lim_p_up = st.number_input("목표: 주차장 → 거주층 (초)", value=50, min_value=10)
    lim_res_p = st.number_input("목표: 거주층 → 주차장 (초)", value=65, min_value=10)

# ----------------- [3] 메인 화면: 제어 패턴 및 수동 배치 -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f 
total_fs = len(FLOOR_LABELS)

st.header("⚙️ 시뮬레이션 환경 및 가동 설정")

# 폼(Form) 구조를 적용하여 버튼 클릭 시 데이터가 증발하는 현상을 차단
with st.form(key="sim_form"):
    c_time, c_custom = st.columns([1, 1])
    
    with c_time:
        st.write("##### ⏰ 시간대별 한전 요금 및 가중치 선택")
        time_options = [
            "새벽 시간대 (00시~06시) [경부하: 78원/kWh]", 
            "출근 시간대 (07시~09시) [최대부하: 195원/kWh]", 
            "낮 시간대 (09시~18시) [중부하: 132원/kWh]", 
            "퇴근 시간대 (18시~20시) [최대부하: 195원/kWh]", 
            "저녁 시간대 (20시~23시) [최대부하: 195원/kWh]"
        ]
        mode_selection = st.radio("시간대 설정", options=time_options, index=1)
        mode_label = mode_selection.split(" (")[0]
        current_is_deliv = True if "새벽" in mode_selection else False
        
        if "78원" in mode_selection:
            kepco_rate = 78.0
        elif "132원" in mode_selection:
            kepco_rate = 132.0
        else:
            kepco_rate = 195.0

    with c_custom:
        st.write("##### ✍️ 연구원 수동 초기 배치 지정")
        m_cols = st.columns(num_elevators)
        manual_placements = []
        for i in range(num_elevators):
            with m_cols[i]:
                val = st.selectbox(
                    f"호기 {chr(65+i)}", 
                    options=range(total_fs), 
                    format_func=lambda x: FLOOR_LABELS[x], 
                    index=idx_1f, 
                    key=f"v_form_f_{i}"
                )
                manual_placements.append(val)
                
    congestion = st.radio(
        "건물 내부 실시간 혼잡도", 
        options=["매우 쾌적", "쾌적", "보통", "혼잡", "매우 혼잡"], 
        index=2, 
        horizontal=True
    )
    delivery_mode = st.toggle("📦 새벽 배달 패널티 가중치 적용", value=current_is_deliv)

    st.divider()
    # 폼 내부의 제출 버튼
    submit_btn = st.form_submit_with_clicked_button(
        label="🚀 동선별 통합 전략 시뮬레이션 가동 및 대조 데이터 산출",
        type="primary",
        use_container_width=True
    )

# ----------------- [4] 알고리즘 맵 및 물리 엔진 코어 -----------------
BASE_ID = "BASE"
STRAT_MAP = {
    BASE_ID: "전략 미적용 (랜덤 운행)",
    "ODD_EVEN": "홀짝수층 분리 운행 전략",
    "ZONE_SPLIT": "고층부/저층부 분할배치 전략",
    "BASE_RETURN": "베이스 스테이션(1F) 강제 복귀",
    "DYNAMIC_GAP": "등간격 동적 분산 배치 전략",
    "AI_OPTIM": f"AI 패턴 예측 사전 배치 ({mode_label})",
    "MANUAL": "사용자 지정 수동 배치 운행"
}

strategies_config = {}
np.random.seed(42)
strategies_config[BASE_ID] = {"placements": list(np.random.randint(0, total_fs, num_elevators)), "logic": "Free"}

oe_placements = []
for i in range(num_elevators):
    if num_elevators == 1:
        oe_placements.append(int(np.random.randint(0, total_fs)))
    elif i % 2 == 0:
        odds = [f for f in range(total_fs) if f <= idx_1f or (f - idx_1f) % 2 != 0]
        oe_placements.append(int(np.random.choice(odds)))
    else:
        evens = [f for f in range(total_fs) if f <= idx_1f or (f - idx_1f) % 2 == 0]
        oe_placements.append(int(np.random.choice(evens)))
strategies_config["ODD_EVEN"] = {"placements": oe_placements, "logic": "Zoning"}

mid_idx = (total_fs + idx_1f) // 2
if num_elevators == 1:
    split_placements = [mid_idx]
else:
    split_placements = [int(idx_1f + (mid_idx-idx_1f)/2) if i < num_elevators/2 else int(mid_idx + (total_fs-mid_idx)/2) for i in range(num_elevators)]
strategies_config["ZONE_SPLIT"] = {"placements": split_placements, "logic": "Split"}

strategies_config["BASE_RETURN"] = {"placements": [idx_1f] * num_elevators, "logic": "Free"}

if num_elevators == 1:
    spacing_placements = [mid_idx]
else:
    spacing_placements = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config["DYNAMIC_GAP"] = {"placements": spacing_placements, "logic": "Free"}

if "새벽" in mode_label:
    ai_pos = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2) if num_elevators > 1 else [idx_1f]
elif "출근" in mode_label:
    r_start = idx_1f + stairs_floor + 1
    r_end = total_fs - 1
    ai_pos = [int(r_start + (r_end - r_start) * (i + 1) / (num_elevators + 1)) if r_start < r_end else r_end for i in range(num_elevators)]
elif "퇴근" in mode_label:
    p_count = int(round(num_elevators * (parking_usage_rate / 100)))
    ai_pos = [0] * p_count + [idx_1f] * (num_elevators - p_count)
elif "저녁" in mode_label:
    l_mid = int(idx_1f + (total_fs - idx_1f) * 0.3)
    ai_pos = [idx_1f if i % 2 == 0 else l_mid for i in range(num_elevators)]
else:
    ai_pos = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config["AI_OPTIM"] = {"placements": ai_pos, "logic": "Free"}

strategies_config["MANUAL"] = {"placements": manual_placements, "logic": "Free"}

def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route_esg_sla(start, end, placements, logic, cong, is_deliv, eff, base_t, fixed_t, p_rate, s_floor, households, is_regen_on):
    if abs(start - end) <= s_floor and start >= idx_1f:
        return 5.0, 0.001
    
    weights = {"매우 쾌적": 0.7, "쾌적": 0.9, "보통": 1.1, "혼잡": 1.8, "매우 혼잡": 2.5}
    w = weights[cong] * (1.0 + (households - 1) * 0.05)
    
    if is_deliv:
        w = w * 1.5
        deliv_penalty = 2.4
        door_penalty = 1.8
    else:
        deliv_penalty = 1.0
        door_penalty = 1.0
    
    avail = [i for i in range(num_elevators)]
    if num_elevators > 1:
        if "Zoning" in logic:
            avail = [i for i in avail if start <= idx_1f or (i % 2 == 0 and start % 2 != 0) or (i % 2 != 0 and start % 2 == 0)]
        elif "Split" in logic:
            mid = (total_fs + idx_1f) // 2
            avail = [i for i in avail if start <= idx_1f or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid)]
    if not avail: avail = [0]
    
    chosen = avail[0]
    min_dist_m = abs(placements[chosen] - start) * floor_height
    wait_t = get_phys_time(min_dist_m, max_velocity, acceleration)
    
    if logic == "BASE_RETURN" and start != idx_1f:
        min_dist_m += (abs(end - idx_1f) * floor_height) 

    move_dist_m = abs(start - end) * floor_height
    move_t = get_phys_time(move_dist_m, max_velocity, acceleration)
    
    if start < idx_1f or end < idx_1f:
        wait_t = wait_t * (1 - (p_rate / 100) * 0.4)
    
    pure_dwell = max(0.0, base_t - fixed_t)
    door_eff_t = fixed_t + (pure_dwell * (1 - (eff/100)))
    if start == idx_1f: 
        door_eff_t = door_eff_t * 1.2
        
    final_time = (wait_t + move_t + (door_eff_t * w)) * (1.3 if is_deliv else 1.0)
    
    total_dist = min_dist_m + move_dist_m
    moving_time_pure = get_phys_time(total_dist, max_velocity, acceleration)
    energy_base = ((500 * 9.8 * max_velocity * moving_time_pure) / (0.85 * 3600 * 1000)) * deliv_penalty
    
    is_upward = (end > start)
    is_heavy = (w >= 1.2 or is_deliv)
    
    if is_regen_on:
        if is_upward and not is_heavy: regen_factor = -0.35
        elif not is_upward and is_heavy: regen_factor = -0.40
        elif is_upward and is_heavy: regen_factor = 1.30
        else: regen_factor = 0.30
    else:
        regen_factor = 1.30 if (is_upward and is_heavy) else 0.05
        
    total_kwh = (energy_base * regen_factor) + (0.001 * w * door_penalty)
    return final_time, total_kwh

# ----------------- [5] 시뮬레이션 연산 및 결과 고정출력 블록 -----------------
infra_state = "작동 중 (신축 스마트 제어)" if regen_enabled else "미사용 (구축 저항 방열)"
st.info(f"🧬 하드웨어 시스템 상태: 회생제동 인버터 **{infra_state}**")

# 버튼 클리커 상태 저장 및 강제 트리거 고정
if submit_btn:
    st.session_state.ready = True
    avg_res_f = int(idx_1f + (max_f - 1) * 0.7)
    
    scenarios_config = {
        "S1": (idx_1f, avg_res_f, lim_1f_up, "1층 ⬆️ 거주층"),
        "S2": (avg_res_f, idx_1f, lim_res_1f, "거주층 ⬇️ 1층"),
        "S3": (0, avg_res_f, lim_p_up, "주차장 ⬆️ 거주층"),
        "S4": (avg_res_f, 0, lim_res_p, "거주층 ⬇️ 주차장")
    }
    
    res_list = []
    for s_code, (start, end, target_sla, s_name) in scenarios_config.items():
        for strat_code, config in strategies_config.items():
            is_base = (strat_code == BASE_ID)
            eff_p = 0 if is_base else button_efficiency
            p_rate_p = 0 if is_base else parking_usage_rate
            s_floor_p = 0 if is_base else stairs_floor
            
            calc_time, calc_kwh = simulate_route_esg_sla(
                start, end, config["placements"], config["logic"], 
                congestion, delivery_mode, eff_p, base_door_time, fixed_door_moving_time,
                p_rate_p, s_floor_p, households_per_floor, regen_enabled
            )
            
            diff = calc_time - target_sla
            sla_pass = 100.0 if diff <= 0 else 0.0
            sla_excess = max(0.0, diff) 
            
            res_list.append({
                "strat_code": strat_code, "strat_name": STRAT_MAP[strat_code],
                "scen_code": s_code, "scen_name": s_name,
                "time": calc_time, "target": target_sla,
                "excess": sla_excess, "pass_rate": sla_pass,
                "kwh": calc_kwh, "cost": calc_kwh * kepco_rate, "co2": calc_kwh * 424.0
            })
    st.session_state.result_df = pd.DataFrame(res_list)
