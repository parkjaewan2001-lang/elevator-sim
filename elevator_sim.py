import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("AI 자동 최적화 로직과 사용자 수동 배치를 한눈에 비교하고 분석합니다.")

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
st.header("⚙️ 시뮬레이션 시나리오 및 배치")

# 1. 시간대 및 비율 설정
c_sc1, c_sc2 = st.columns(2)
with c_sc1:
    mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], horizontal=True)
with c_sc2:
    delivery_mode = st.toggle("📦 택배 배달 지연 모드 활성화")

st.subheader("🚗 주차장(지하) 이용 비중")
c_p1, c_p2 = st.columns(2)
with c_p1: p_up_ratio = st.slider("지하에서 올라가는 비율 (%)", 0, 100, 30)
with c_p2: p_down_ratio = st.slider("지하로 내려가는 비율 (%)", 0, 100, 40)

st.divider()

# 2. 배치 모드 선택 (핵심 수정 사항)
placement_mode = st.radio(
    "📍 배치 방식 선택", 
    ["AI 자동 최적화 분석 (코드 기반)", "사용자 수동 배치 시뮬레이션"], 
    horizontal=True,
    help="AI 모드는 시간대와 수요를 분석하여 최적 위치를 제안하며, 수동 모드는 사용자가 직접 위치를 결정합니다."
)

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

# 배치 결정 로직
final_placements = []
if placement_mode == "사용자 수동 배치 시뮬레이션":
    st.info("각 엘리베이터의 대기 위치를 직접 지정하세요.")
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            final_placements.append(val)
else:
    # AI 최적화 로직 (코드 기반 자동 분석)
    if mode_label == "출근 시간": # 거주층 상층부 분산
        final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    elif mode_label == "퇴근 시간": # 1F 및 지하 주차장 집중
        num_b = int(num_elevators * (max(p_up_ratio, p_down_ratio) / 100))
        final_placements = [random.randint(0, idx_1f-1) for _ in range(num_b)] + [idx_1f] * (num_elevators - num_b)
    else: # 균등 분산
        final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    
    st.success(f"🤖 AI가 '{mode_label}' 패턴을 분석하여 최적 위치를 산출했습니다.")
    cols = st.columns(num_elevators)
    for i, p in enumerate(final_placements):
        cols[i].metric(f"EL {chr(65+i)} 제안 위치", FLOOR_LABELS[p])

run_btn = st.button("🚀 전체 성능 데이터 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: ENGINE -----------------

def calculate_time(start_idx, end_idx, placements, is_optimized):
    # 대기 거리 계산 (비최적화 대조군 대비 성능 측정을 위해)
    min_dist = min([abs(f_idx - start_idx) for f_idx in placements])
    
    # 가속도 물리 엔진 반영
    wait_t = (min_dist * sec_per_floor) + accel_delay
    move_t = (abs(start_idx - end_idx) * sec_per_floor) + accel_delay
    
    # 혼잡도 및 세대수 가중치
    household_weight = 1 + (households_per_floor * 0.03)
    total = (wait_t + move_t + (door_time * 2) + (1.2 * 4)) * household_weight
    if delivery_mode: total *= 1.3
    return total

if run_btn:
    # 대조군 (전략 없음: 모두 1층 대기)
    basic_placements = [idx_1f] * num_elevators
    
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    nodes = {
        "1F ⬆️ 거주층": (idx_1f, avg_res_f, t_1f_up),
        "거주층 ⬇️ 1F": (avg_res_f, idx_1f, t_1f_down),
        "지하 ⬆️ 거주층": (0, avg_res_f, t_b_up),
        "거주층 ⬇️ 지하": (avg_res_f, 0, t_b_down)
    }

    st.subheader("📊 성능 분석 리포트")
    m_cols = st.columns(4)
    report_data = []
    
    for i, (name, (start, end, target)) in enumerate(nodes.items()):
        current_time = calculate_time(start, end, final_placements, True)
        basic_time = calculate_time(start, end, basic_placements, False)
        diff = current_time - basic_time
        
        with m_cols[i]:
            st.metric(name, f"{current_time:.1f}초", f"{diff:+.1f}초 (전략 미적용 대비)", delta_color="inverse")
        
        status = f"✅ {abs(current_time - target):.1f}초 단축" if current_time <= target else f"⚠️ {current_time - target:.1f}초 초과"
        report_data.append({
            "분석 노선": name, 
            "목표 시간": f"{target}초", 
            "현재 예상": f"{current_time:.1f}초", 
            "기본(1F대기)": f"{basic_time:.1f}초",
            "성과": status
        })

    st.divider()
    c_l, c_r = st.columns([1, 2])
    with c_l:
        st.write("#### 📍 시뮬레이션 배치 정보")
        for j, p in enumerate(final_placements):
            st.write(f"**엘리베이터 {chr(65+j)}**: {FLOOR_LABELS[p]}")
        st.info(f"선택 모드: {placement_mode}")
    
    with c_r:
        st.write("#### 📋 노선별 상세 데이터")
        st.table(pd.DataFrame(report_data))
