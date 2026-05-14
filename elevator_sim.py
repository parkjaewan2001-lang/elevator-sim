import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("사용자 정의 배치와 비최적화(기본) 상태의 성능 차이를 정밀 분석합니다.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 거주 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (분석 제외)", 1, 5, 3)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10)

    st.divider()

    st.header("⚡ 물리 및 가속도 설정")
    sec_per_floor = st.number_input("정속 주행 시 층당 시간(초)", value=1.0)
    accel_delay = st.number_input("가속/감속 추가 지연(초)", value=1.5)
    door_time = st.number_input("문 개폐 시간(초)", value=7.0)

    st.divider()
    
    st.header("🎯 목표 시간(초)")
    t_1f_up = st.number_input("1F → 거주층 목표", value=45)
    t_1f_down = st.number_input("거주층 → 1F 목표", value=80)
    t_b_up = st.number_input("지하 → 거주층 목표", value=55)
    t_b_down = st.number_input("거주층 → 지하 목표", value=90)

# ----------------- MAIN PANEL: SCENARIO SETTINGS -----------------
st.header("⚙️ 시뮬레이션 시나리오")

# 1. 시간대 설정
mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], horizontal=True)
current_mode = mode_label

# 2. 주차장 이용 비율 설정
st.subheader("🚗 주차장(지하) 이용 비중 설정")
c_p1, c_p2 = st.columns(2)
with c_p1: p_up_ratio = st.slider("지하에서 올라가는 비율 (%)", 0, 100, 30)
with c_p2: p_down_ratio = st.slider("지하로 내려가는 비율 (%)", 0, 100, 40)

# 3. 기타 변수
col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    congestion_level = st.select_slider("👥 건물 혼잡도", options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡"], value="보통")
with col_cfg2:
    delivery_mode = st.toggle("📦 택배 배달 지연 모드 활성화")

# 가중치 계산
congestion_map = {"매우 쾌적": 0.8, "여유": 1.0, "보통": 1.2, "혼잡": 2.0, "매우 혼잡": 3.5}
adj_delay = congestion_map[congestion_level]
household_weight = 1 + (households_per_floor * 0.03)

st.divider()

# 4. 사용자 직접 배치 설정
st.subheader("📍 엘리베이터 수동 배치 (사용자 정의)")
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

user_placements = []
m_cols = st.columns(num_elevators)
for i in range(num_elevators):
    with m_cols[i]:
        val = st.selectbox(f"EL {chr(65+i)} 위치", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
        user_placements.append(val)

run_btn = st.button("🚀 사용자 배치 vs 비최적화 비교 분석", type="primary", use_container_width=True)

# ----------------- LOGIC: ENGINE -----------------

def get_wait_dist(start_idx, placements, is_basic_fixed):
    """
    is_basic_fixed=True일 경우: 모든 EL이 1층에 고정된 비최적화 상태
    is_basic_fixed=False일 경우: 사용자가 배치한 위치 기준
    """
    if is_basic_fixed:
        # 비최적화(1층 고정) 시에도 대수가 많으면 확률적으로 응답 효율 상승 (군집 효과)
        base_dist = abs(idx_1f - start_idx)
        efficiency = max(0.4, (1 - (0.15 * (len(placements) - 1))))
        return base_dist * efficiency
    else:
        # 사용자 배치 위치 중 가장 가까운 거리 계산
        return min([abs(f_idx - start_idx) for f_idx in placements])

def calculate_time(start_idx, end_idx, placements, is_basic_fixed):
    d_call = get_wait_dist(start_idx, placements, is_basic_fixed)
    wait_t = (d_call * sec_per_floor) + accel_delay
    
    d_move = abs(start_idx - end_idx)
    move_t = (d_move * sec_per_floor) + accel_delay
    
    total = (wait_t + move_t + (door_time * 2) + (1.2 * 4 * adj_delay)) * household_weight
    if delivery_mode: total *= 1.3
    return total

if run_btn:
    # 대조군 설정 (비최적화: 전원 1층 대기)
    basic_placements = [idx_1f] * num_elevators
    
    # 성능 분석 노선
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    nodes = {
        "1F ⬆️ 거주층": (idx_1f, avg_res_f, t_1f_up),
        "거주층 ⬇️ 1F": (avg_res_f, idx_1f, t_1f_down),
        "지하 ⬆️ 거주층": (0, avg_res_f, t_b_up),
        "거주층 ⬇️ 지하": (avg_res_f, 0, t_b_down)
    }

    # 리포트 출력
    st.subheader(f"📊 분석 결과 리포트")
    
    m_cols = st.columns(4)
    report_data = []
    
    for i, (name, (start, end, target)) in enumerate(nodes.items()):
        # 사용자 배치 시간
        user_time = calculate_time(start, end, user_placements, False)
        # 비최적화(기본) 시간
        basic_time = calculate_time(start, end, basic_placements, True)
        
        diff_from_basic = user_time - basic_time
        
        with m_cols[i]:
            st.metric(name, f"{user_time:.1f}초", f"{diff_from_basic:+.1f}초 (기본대비)", delta_color="inverse")
        
        status = f"✅ {abs(user_time - target):.1f}초 단축" if user_time <= target else f"⚠️ {user_time - target:.1f}초 초과"
        report_data.append({
            "노선": name, 
            "목표": f"{target}초", 
            "사용자 배치": f"{user_time:.1f}초", 
            "비최적화(기본)": f"{basic_time:.1f}초",
            "비교 결과": status
        })

    st.divider()
    c_l, c_r = st.columns([1, 2])
    
    with c_l:
        st.write("#### 📍 설정된 대기 층수")
        for j, p in enumerate(user_placements):
            st.write(f"**EL {chr(65+j)}**: {FLOOR_LABELS[p]}")
        
        st.info("💡 **비교 안내:** 상단의 델타(+) 수치는 모든 엘리베이터가 1층에 대기하는 '비최적화' 상태 대비 사용자 배치의 효율을 나타냅니다.")

    with c_r:
        st.write("#### 📋 노선별 상세 비교 데이터")
        st.table(pd.DataFrame(report_data))

    # 차트: 사용자 배치의 효율성 시각화
    st.write("#### 📈 사용자 배치 vs 비최적화 성능 비교 (전 노선)")
    chart_df = pd.DataFrame(report_data)
    chart_df["사용자"] = chart_df["사용자 배치"].str.replace("초", "").astype(float)
    chart_df["기본(비최적화)"] = chart_df["비최적화(기본)"].str.replace("초", "").astype(float)
    st.bar_chart(chart_df.set_index("노선")[["사용자", "기본(비최적화)"]])
