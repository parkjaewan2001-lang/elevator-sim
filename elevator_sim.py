import streamlit as st
import pandas as pd
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("물리 엔진, 주차장 동선, 그리고 '실시간 혼잡도'가 결합된 통합 시뮬레이터입니다.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 기본 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10, step=1)

    st.divider()

    st.header("⚡ 물리 및 가속도 설정")
    sec_per_floor = st.number_input("정속 주행 시 층당 시간(초)", value=1.0, step=0.1)
    accel_delay = st.number_input("가속/감속 추가 지연(초)", value=1.5)
    door_time = st.number_input("문 개폐 시간(초)", value=7.0, step=0.5)

    st.divider()
    
    st.header("🎯 동선별 목표 시간(초)")
    target_1f_up = st.number_input("1F → 거주층 목표", value=45)
    target_1f_down = st.number_input("거주층 → 1F 목표", value=80)
    target_b_up = st.number_input("지하 → 거주층 목표", value=55)
    target_b_down = st.number_input("거주층 → 지하 목표", value=90)

# ----------------- MAIN PANEL -----------------
st.header("⚙️ 시뮬레이션 설정")

# [신규 기능] 혼잡도 조정
st.subheader("👥 엘리베이터 혼잡도 설정")
congestion_level = st.select_slider(
    "현재 건물의 혼잡 상태를 선택하세요",
    options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡(지연 발생)"],
    value="보통"
)

# 혼잡도에 따른 가중치 계산
congestion_map = {
    "매우 쾌적": {"delay": 0.8, "stops": 1},
    "여유": {"delay": 1.0, "stops": 1.2},
    "보통": {"delay": 1.2, "stops": 1.5},
    "혼잡": {"delay": 2.0, "stops": 2.2},
    "매우 혼잡(지연 발생)": {"delay": 3.5, "stops": 3.0}
}
adj_delay = congestion_map[congestion_level]["delay"]
adj_stops = congestion_map[congestion_level]["stops"]

st.info(f"💡 **혼잡도 영향:** 현재 '{congestion_level}' 상태로 인해 승하차 시간이 평소의 {adj_delay}배로 늘어나며, 중간 정차 확률이 높아집니다.")

st.divider()

mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], horizontal=True)
mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "낮 시간": "daytime", "새벽 시간": "night"}
current_mode = mode_map[mode_label]

placement_method = st.radio("📍 배치 방식", ["자동 최적화 추천", "사용자 수동 배치"], horizontal=True)

# 층 설정 및 주차장 비율
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

p_ratio = st.slider("🚗 주차장(지하층) 이용 비중 (%)", 0, 100, 30)

# 수동 배치 입력
manual_floors = []
if placement_method == "사용자 수동 배치":
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            manual_floors.append(val)

run_btn = st.button("🚀 혼잡도 반영 정밀 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: PHYSICS ENGINE -----------------
def calc_travel_time(dist):
    if dist <= 0: return 0
    # 중간 정차 가중치를 반영하여 거리당 가속/감속 지연 중첩 계산
    return (dist * sec_per_floor) + (accel_delay * adj_stops)

if run_btn:
    # 1. 배치 결정
    best_floors = []
    if placement_method == "자동 최적화 추천":
        if current_mode == "morning":
            step = (total_fs - idx_1f) // (num_elevators + 1)
            best_floors = [int(idx_1f + (step * (i+1))) for i in range(num_elevators)]
        elif current_mode == "evening":
            num_to_b = int(num_elevators * (p_ratio / 100))
            best_floors = [random.randint(0, idx_1f-1) for _ in range(num_to_b)] + [idx_1f] * (num_elevators - num_to_b)
        else:
            step = total_fs // (num_elevators + 1)
            best_floors = [int(step * (i+1)) for i in range(num_elevators)]
    else:
        best_floors = manual_floors

    # 2. 대기 위치 표시
    st.subheader("📍 엘리베이터 대기 위치")
    cols = st.columns(num_elevators)
    for i, f_idx in enumerate(best_floors):
        cols[i].metric(f"엘리베이터 {chr(65+i)}", FLOOR_LABELS[f_idx])

    # 3. 성능 계산 (혼잡도 가중치 적용)
    avg_high_f = idx_1f + (max_f * 0.6) 
    
    def analyze_node(start_idx, end_idx, target):
        min_dist = min([abs(f_idx - start_idx) for f_idx in best_floors])
        wait_time = calc_travel_time(min_dist)
        move_time = calc_travel_time(abs(start_idx - end_idx))
        
        # 총 시간 = 대기 + 이동 + 문개폐 + (인당 지연 * 혼잡도 가중치)
        total = wait_time + move_time + (door_time * 2) + (1.2 * 4 * adj_delay)
        return total, total - target

    nodes = {
        "1F → 거주층": analyze_node(idx_1f, avg_high_f, target_1f_up),
        "거주층 → 1F": analyze_node(avg_high_f, idx_1f, target_1f_down),
        "지하 → 거주층": analyze_node(0, avg_high_f, target_b_up),
        "거주층 → 지하": analyze_node(avg_high_f, 0, target_b_down)
    }

    # 4. 결과 리포트
    st.divider()
    st.subheader(f"🔍 분석 리포트 (상태: {congestion_level})")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("#### 🏢 지상 1층 로비 동선")
        st.metric("1F ⬆️ 상행", f"{nodes['1F → 거주층'][0]:.1f}초", f"{nodes['1F → 거주층'][1]:+.1f}초", delta_color="inverse")
        st.metric("1F ⬇️ 하행", f"{nodes['거주층 → 1F'][0]:.1f}초", f"{nodes['거주층 → 1F'][1]:+.1f}초", delta_color="inverse")
    
    with col_b:
        st.write("#### 🚗 지하 주차장 동선")
        st.metric("지하 ⬆️ 상행", f"{nodes['지하 → 거주층'][0]:.1f}초", f"{nodes['지하 → 거주층'][1]:+.1f}초", delta_color="inverse")
        st.metric("지하 ⬇️ 하행", f"{nodes['거주층 → 지하'][0]:.1f}초", f"{nodes['거주층 → 지하'][1]:+.1f}초", delta_color="inverse")

    st.write("#### 📋 상세 분석 데이터")
    report_data = []
    for name, (time, diff) in nodes.items():
        status = f"✅ {abs(diff):.1f}초 단축" if diff <= 0 else f"⚠️ {diff:.1f}초 초과"
        report_data.append({"노선": name, "예상 시간": f"{time:.1f}초", "상태": status})
    st.table(pd.DataFrame(report_data))
