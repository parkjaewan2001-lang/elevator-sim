import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")
st.caption("물리적 가속도 엔진과 사용자 행동 패턴이 결합된 최종 정밀 시뮬레이터입니다.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 거주 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (분석 제외)", 1, 5, 3)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=2, max_value=10)

    st.divider()

    # [부활] 물리 엔진 설정: 속도 및 가속도
    st.header("🚀 물리 엔진 설정")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5, help="엘리베이터의 최고 이동 속도")
    acceleration = st.number_input("가속도 (m/s²)", value=1.0, help="최고 속도까지 도달하는 가속 정도")

    st.divider()

    st.header("⚡ 문 개폐 및 행동 설정")
    base_door_time = st.number_input("기본 문 개폐 시간 (초)", value=7.0)
    button_efficiency = st.slider("🔘 닫힘 버튼 사용 효율 (%)", 0, 100, 40)

    st.divider()
    
    st.header("⚠️ 최대 허용 대기 시간 (초)")
    limit_1f_up = st.slider("1F → 거주층 최대치", 30, 120, 50)
    limit_1f_down = st.slider("거주층 → 1F 최대치", 30, 180, 80)
    limit_b_up = st.slider("지하 → 거주층 최대치", 30, 150, 60)
    limit_b_down = st.slider("거주층 → 지하 최대치", 30, 180, 90)

# ----------------- MAIN PANEL: SCENARIO SETTINGS -----------------
st.header("⚙️ 시나리오 및 운영 알고리즘 설정")

col_sc1, col_sc2 = st.columns(2)
with col_sc1:
    logic_type = st.radio("🕹️ 운영 알고리즘 (군집 제어)", ["전 층 자유 운행 (기본)", "홀짝수층 분리 운행", "저층/고층부 분할 운행"], horizontal=True)
    mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간"], horizontal=True)

with col_sc2:
    congestion_level = st.select_slider("👥 건물 혼잡도 설정", options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡"], value="보통")
    delivery_mode = st.toggle("📦 택배 배달 지연 모드 활성화")

st.divider()

# 배치 방식 결정
placement_mode = st.radio("📍 대기 위치 결정 방식", ["AI 자동 최적화 배치", "사용자 수동 배치"], horizontal=True)

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

final_placements = []
if placement_mode == "사용자 수동 배치":
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            final_placements.append(val)
else:
    if mode_label == "출근 시간":
        final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    elif mode_label == "퇴근 시간":
        num_b = int(num_elevators * (max(p_up_ratio, p_down_ratio) / 100 if 'p_up_ratio' in locals() else 0.3))
        final_placements = [random.randint(0, idx_1f-1) for _ in range(num_b)] + [idx_1f] * (num_elevators - num_b)
    else:
        final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    
    cols = st.columns(num_elevators)
    for i, p in enumerate(final_placements):
        cols[i].metric(f"EL {chr(65+i)} 배치", FLOOR_LABELS[p])

run_btn = st.button("🚀 통합 물리 엔진 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: PHYSICS ENGINE -----------------

def get_travel_time(distance_m, v_max, a):
    """물리 법칙(가속도)을 반영한 순수 이동 시간 계산"""
    if distance_m == 0: return 0
    # 최고 속도에 도달하기 위해 필요한 거리: d = v^2 / (2a)
    d_accel = (v_max ** 2) / (2 * a)
    
    if distance_m >= 2 * d_accel:
        # 가속 -> 정속 -> 감속 구간이 모두 존재하는 경우
        t_accel = v_max / a
        t_const = (distance_m - (2 * d_accel)) / v_max
        return (2 * t_accel) + t_const
    else:
        # 최고 속도에 도달하지 못하고 바로 감속해야 하는 경우 (삼각형 프로파일)
        return 2 * np.sqrt(distance_m / a)

def calculate_physics_time(start_idx, end_idx, placements, logic, cong, is_deliv, eff):
    c_map = {"매우 쾌적": 0.7, "여유": 0.9, "보통": 1.1, "혼잡": 1.6, "매우 혼잡": 2.5}
    w = c_map[cong]
    
    # 1. 응답 가능한 엘리베이터 필터링
    from __main__ import get_reachable_elevators # 내부 함수 참조
    avail_indices = get_reachable_elevators(start_idx, logic, len(placements))
    avail_placements = [placements[i] for i in avail_indices]
    min_dist_floors = min([abs(f_idx - start_idx) for f_idx in avail_placements])
    
    # 2. 물리 이동 시간 계산 (층간 높이 반영)
    wait_m = min_dist_floors * floor_height
    move_m = abs(start_idx - end_idx) * floor_height
    
    wait_t = get_travel_time(wait_m, max_velocity, acceleration)
    move_t = get_travel_time(move_m, max_velocity, acceleration)
    
    # 3. 문 개폐 및 행동 로직
    is_passenger_inside = True if start_idx > idx_1f else False
    actual_door_t = base_door_time * (1 - (eff / 100)) if is_passenger_inside else base_door_time * 1.2
    
    h_weight = 1 + (households_per_floor * 0.05)
    loading_t = (actual_door_t * w) * h_weight
    
    total = (wait_t + move_t + loading_t)
    if is_deliv: total *= 1.3
    return total, actual_door_t

# 헬퍼 함수
def get_reachable_elevators(target_floor_idx, logic, num_els):
    available = []
    actual_floor = target_floor_idx - min_f 
    for i in range(num_els):
        if logic == "전 층 자유 운행 (기본)": available.append(i)
        elif logic == "홀짝수층 분리 운행":
            if target_floor_idx == idx_1f or (i % 2 == 0 and actual_floor % 2 != 0) or (i % 2 != 0 and actual_floor % 2 == 0): available.append(i)
        elif logic == "저층/고층부 분할 운행":
            mid = total_fs // 2
            if target_floor_idx == idx_1f or (i < num_els/2 and target_floor_idx <= mid) or (i >= num_els/2 and target_floor_idx > mid): available.append(i)
    return available if available else list(range(num_els))

if run_btn:
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    nodes = {"1F ⬆️ 거주층": (idx_1f, avg_res_f, limit_1f_up), "거주층 ⬇️ 1F": (avg_res_f, idx_1f, limit_1f_down),
             "지하 ⬆️ 거주층": (0, avg_res_f, limit_b_up), "거주층 ⬇️ 지하": (avg_res_f, 0, limit_b_down)}

    st.subheader(f"📊 물리 엔진 분석 결과 (속도: {max_velocity}m/s, 가속도: {acceleration}m/s²)")
    m_cols = st.columns(4)
    report_list, chart_data = [], []

    for i, (name, (start, end, limit)) in enumerate(nodes.items()):
        strategy_t, door_t = calculate_physics_time(start, end, final_placements, logic_type, congestion_level, delivery_mode, button_efficiency)
        
        # 무작위 분산 대조군
        results_r = [calculate_physics_time(start, end, [random.randint(0, total_fs-1) for _ in range(num_elevators)], logic_type, congestion_level, delivery_mode, button_efficiency)[0] for _ in range(10)]
        random_t = sum(results_r) / 10
        
        is_exceed = strategy_t > limit
        with m_cols[i]:
            st.metric(name, f"{strategy_t:.1f}초", f"한계: {limit}초", delta_color="normal" if not is_exceed else "inverse")
            if is_exceed: st.error("🚨 임계치 초과")
            else: st.success("✅ 통과")
        
        report_list.append({"노선": name, "전략 적용": f"{strategy_t:.1f}초", "무작위 대비": f"{strategy_t-random_t:+.1f}초", "상태": "안정" if not is_exceed else "위험"})
        chart_data.append({"노선": name, "현재 전략": strategy_t, "최대 허용치": limit, "무작위 분산": random_t})

    st.divider()
    c_chart, c_info = st.columns([2, 1])
    with c_chart:
        st.write("#### 📈 노선별 시간 비교")
        st.bar_chart(pd.DataFrame(chart_data).set_index("노선"))
    with c_info:
        st.info(f"💡 **물리 엔진 작동:** 설정된 {max_velocity}m/s 속도와 {acceleration}m/s² 가속도를 기반으로 거리에 따른 도달 시간을 실시간 계산 중입니다.")

    st.table(pd.DataFrame(report_list))
