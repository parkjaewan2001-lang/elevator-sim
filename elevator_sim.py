import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")
st.caption("제약 없는 알고리즘 조합과 세밀한 노선별 임계치 설정이 가능한 통합 시뮬레이터입니다.")

# ----------------- SIDEBAR: 물리 및 건물 설정 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (분석 제외)", 1, 5, 3)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=2, max_value=10)

    st.divider()
    st.header("🚀 물리 엔진 설정")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)

    st.divider()
    st.header("⚡ 문 개폐 및 행동 설정")
    base_door_time = st.number_input("기본 문 개폐 시간 (초)", value=7.0)
    button_efficiency = st.slider("🔘 닫힘 버튼 사용 효율 (%)", 0, 100, 40)

    st.divider()
    st.header("⚠️ 노선별 서비스 임계치 (SLA)")
    lim_1f_up = st.slider("1층 → 거주층 (상행)", 30, 180, 60)
    lim_res_1f = st.slider("거주층 → 1층 (하행)", 30, 180, 80)
    lim_p_up = st.slider("주차장 → 거주층 (상행)", 30, 180, 70)
    lim_res_p = st.slider("거주층 → 주차장 (하행)", 30, 180, 90)

# ----------------- MAIN PANEL: 제약 없는 자유 조합 -----------------
st.header("⚙️ 시나리오 및 전략 자유 조합")

# 층 레이블 생성
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

col_strat1, col_strat2 = st.columns(2)

with col_strat1:
    st.subheader("🕹️ 운영 알고리즘 선택")
    logic_type = st.selectbox(
        "운행 규칙 (군집 제어)",
        ["전 층 자유 운행 (기본)", "홀짝수층 분리 운행", "저층/고층부 분할 운행"]
    )
    st.info("💡 선택한 알고리즘 규칙에 따라 호출에 응답할 엘리베이터가 결정됩니다.")

with col_strat2:
    st.subheader("📍 대기 위치 배치 전략")
    placement_method = st.radio("배치 방식", ["AI 자동 최적화", "사용자 수동 배치"], horizontal=True)
    mode_label = st.select_slider("⏰ 시간대 패턴 설정", options=["새벽 시간", "출근 시간", "낮 시간", "퇴근 시간"], value="낮 시간")

# 배치 확정 로직
final_placements = []
if placement_method == "사용자 수동 배치":
    st.write("**엘리베이터별 대기층 수동 지정**")
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            final_placements.append(val)
else:
    # 시간대별 AI 배치 로직
    if mode_label == "새벽 시간":
        final_placements = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2)
    elif mode_label == "출근 시간":
        final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    elif mode_label == "퇴근 시간":
        final_placements = [idx_1f] * num_elevators
    else: # 낮 시간
        final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    
    st.write("**AI 추천 대기 위치**")
    p_cols = st.columns(num_elevators)
    for i, p in enumerate(final_placements):
        p_cols[i].metric(f"EL {chr(65+i)}", FLOOR_LABELS[p])

st.divider()

st.subheader("🌐 환경 및 지연 가중치")
c_env1, c_env2, c_env3 = st.columns(3)
with c_env1: congestion = st.select_slider("건물 혼잡도", options=["매우 쾌적", "보통", "매우 혼잡"], value="보통")
with c_env2: delivery = st.toggle("📦 배송/택배 지연 모드 활성화", value=(mode_label == "새벽 시간"))
with c_env3: dynamic_door = st.toggle("🚪 동적 문 개폐 로직 적용", value=True)

# ----------------- LOGIC: 통합 시뮬레이션 엔진 -----------------

def get_travel_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel:
        return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    else:
        return 2 * np.sqrt(dist_m / accel)

def calculate_complex_time(start, end, placements, logic, cong, is_deliv, eff, door_active):
    c_map = {"매우 쾌적": 0.7, "보통": 1.1, "매우 혼잡": 2.5}
    w = c_map[cong]
    
    # 1. 알고리즘에 따른 응답 가능 엘리베이터 필터링
    actual_f = start - min_f
    avail = []
    for i in range(num_elevators):
        if logic == "전 층 자유 운행 (기본)":
            avail.append(i)
        elif logic == "홀짝수층 분리 운행":
            if start == idx_1f or (i % 2 == 0 and actual_f % 2 != 0) or (i % 2 != 0 and actual_f % 2 == 0):
                avail.append(i)
        elif logic == "저층/고층부 분할 운행":
            mid = total_fs // 2
            if start == idx_1f or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid):
                avail.append(i)
    
    if not avail: avail = list(range(num_elevators))
    
    # 2. 물리적 대기 시간 (가장 가까운 엘리베이터)
    min_dist_m = min([abs(placements[i] - start) for i in avail]) * floor_height
    wait_t = get_travel_time(min_dist_m, max_velocity, acceleration)
    
    # 3. 물리적 이동 시간
    move_t = get_travel_time(abs(start - end) * floor_height, max_velocity, acceleration)
    
    # 4. 동적 문 개폐 시간 (하행 시에만 닫힘 버튼 효과)
    is_inside = True if start > idx_1f else False
    if door_active and is_inside:
        door_t = base_door_time * (1 - (eff / 100))
    else:
        door_t = base_door_time * 1.2 # 하차 후 혹은 빈 차 호출 시 자동 닫힘 지연
    
    # 5. 밀도 및 혼잡도 반영
    loading_t = (door_t * w) * (1 + (households_per_floor * 0.05))
    
    total = wait_t + move_t + loading_t
    if is_deliv: total *= 1.4 if mode_label == "새벽 시간" else 1.3
    return total

# ----------------- RESULT EXECUTION -----------------
if st.button("🚀 전체 노선 통합 정밀 분석 실행", type="primary", use_container_width=True):
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.7)
    
    # 4대 노선 시나리오
    scenarios = {
        "1층 ⬆️ 거주층": (idx_1f, avg_res_f, lim_1f_up),
        "거주층 ⬇️ 1층": (avg_res_f, idx_1f, lim_res_1f),
        "주차장 ⬆️ 거주층": (0, avg_res_f, lim_p_up),
        "거주층 ⬇️ 주차장": (avg_res_f, 0, lim_res_p)
    }

    st.subheader(f"📊 {mode_label} 시뮬레이션 결과 리포트")
    m_cols = st.columns(4)
    chart_data = []

    for i, (name, (s, e, l)) in enumerate(scenarios.items()):
        res_t = calculate_complex_time(s, e, final_placements, logic_type, congestion, delivery, button_efficiency, dynamic_door)
        is_exceed = res_t > l
        
        with m_cols[i]:
            st.metric(name, f"{res_t:.1f}초", f"목표 {l}s", delta_color="normal" if not is_exceed else "inverse")
            if is_exceed: st.error("🚨 목표 시간 초과")
            else: st.success("✅ 서비스 만족")
        
        chart_data.append({"노선": name, "소요 시간": res_t, "SLA 임계치": l})

    st.divider()
    st.write("#### 📈 노선별 시간 분석 그래프")
    st.bar_chart(pd.DataFrame(chart_data).set_index("노선"))
    
    st.info(f"📍 **적용 전략 요약:** 알고리즘({logic_type}), 배치({mode_label} 패턴), 가속도({acceleration}m/s²), 세대밀도({households_per_floor})")
