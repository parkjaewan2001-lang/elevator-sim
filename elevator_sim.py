import streamlit as st
import random
import pandas as pd

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Realistic Elevator Simulator", layout="wide")

st.title("🏢 Realistic Elevator Simulator")
st.caption("물리적 한계를 고려하여 목표 시간 대비 지연 상황을 솔직하게 보고합니다.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 기본 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, step=1)
    num_elevators = st.number_input("엘리베이터 개수", value=2, step=1)

    st.divider()

    st.header("⚡ 물리 및 지연 설정")
    # 지연 시간 입력 (숫자 직접 입력)
    st.write("인당 탑승/하차 지연 시간(초)")
    delay_col1, delay_col2 = st.columns([1.5, 1])
    with delay_col1:
        preset = st.selectbox("프리셋 선택", ["직접 입력", "쾌적(0.8)", "보통(1.2)", "혼잡(2.5)"])
        preset_map = {"직접 입력": 1.2, "쾌적(0.8)": 0.8, "보통(1.2)": 1.2, "혼잡(2.5)": 2.5}
    with delay_col2:
        boarding_delay = st.number_input("지연 초", value=preset_map[preset], step=0.1, format="%.1f")
    
    sec_per_floor = st.number_input("한 층 이동 시간(초)", value=2.5, step=0.1)
    door_time = st.number_input("문 개폐 시간(초)", value=7.0, step=0.5)

    st.divider()
    
    st.header("🎯 동선별 희망 목표 시간 (초)")
    hc1, hc2 = st.columns(2)
    with hc1:
        t_1f_to_res = st.number_input("1F → 거주층", value=45)
        t_res_to_1f = st.number_input("거주층 → 1F", value=80)
    with hc2:
        t_b_to_res = st.number_input("B → 거주층", value=55)
        t_res_to_b = st.number_input("거주층 → B", value=90)

# ----------------- MAIN PANEL -----------------
st.header("⚙️ 시나리오 및 비율 설정")
mode_col, ratio_col = st.columns([1, 1])

with mode_col:
    mode_label = st.radio("⏰ 시간대 선택", ["출근 시간", "퇴근 시간", "그 외 시간"], horizontal=True)
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "그 외 시간": "other"}
    current_mode = mode_map[mode_label]

with ratio_col:
    if current_mode == "morning":
        p_ratio = st.number_input("출근 시 주차장(지하) 하차 비율 (%)", min_value=0, max_value=100, value=40, step=1)
    elif current_mode == "evening":
        p_ratio = st.number_input("퇴근 시 주차장(지하) 승차 비율 (%)", min_value=0, max_value=100, value=30, step=1)
    else:
        p_ratio = 50

st.divider()
run_btn = st.button("🚀 현실적 지연 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC & REALISTIC CALCULATION -----------------
if run_btn:
    # 1. 층 레이블 및 1층 위치 설정
    FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
    idx_1f = min_f
    avg_floor_dist = (max_f / 2) # 평균 이동 층수 (중간층 기준)

    # 2. 물리적 예상 시간 계산 함수 (핵심 로직)
    def calculate_realistic_time(start_idx, end_idx):
        # 이동 시간 = 층수 차이 * 층당 이동 시간
        travel_time = abs(start_idx - end_idx) * sec_per_floor
        # 정지 및 개폐 시간 = 문 개폐 시간 * 2 (출발지, 목적지)
        stop_time = door_time * 2
        # 탑승객 지연 = 세대당 발생 확률을 고려한 가중치 (평균 2명 탑승 가정)
        pax_delay = boarding_delay * 2 * 2 # (승차 시 2명 + 하차 시 2명)
        return travel_time + stop_time + pax_delay

    # 각 동선별 예상 시간 산출 (평균적으로 중간층인 max_f/2 지점 이동 가정)
    est_1f_to_res = calculate_realistic_time(idx_1f, idx_1f + avg_floor_dist)
    est_b_to_res = calculate_realistic_time(0, idx_1f + avg_floor_dist)
    est_res_to_1f = calculate_realistic_time(idx_1f + avg_floor_dist, idx_1f)
    est_res_to_b = calculate_realistic_time(idx_1f + avg_floor_dist, 0)

    # 3. 목표 달성 여부 및 오차 계산 함수
    def check_perf(est, target):
        diff = est - target
        if diff <= 0:
            return f"{est:.1f}초", "✅ 달성", "정상"
        else:
            return f"{est:.1f}초", f"⚠️ {diff:.1f}초 지연", "지연됨"

    # 결과 데이터 생성
    paths = ["1층 → 거주층", "주차장 → 거주층", "거주층 → 1층", "거주층 → 주차장"]
    targets = [t_1f_to_res, t_b_to_res, t_res_to_1f, t_res_to_b]
    estimates = [est_1f_to_res, est_b_to_res, est_res_to_1f, est_res_to_b]
    
    results = [check_perf(e, t) for e, t in zip(estimates, targets)]

    # 4. 결과 출력
    st.subheader(f"📊 {mode_label} 현실적 성능 분석 리포트")
    
    # 표 데이터 구성
    perf_df = pd.DataFrame({
        "이동 동선": paths,
        "설정된 목표": [f"{t}초" for t in targets],
        "물리적 예상시간": [r[0] for r in results],
        "상태 및 지연시간": [r[1] for r in results]
    })
    
    # 스타일 적용하여 출력
    st.table(perf_df)

    # 분석 의견
    st.divider()
    st.subheader("🔍 분석 의견")
    
    delayed_count = sum(1 for r in results if "지연" in r[1])
    if delayed_count > 0:
        st.error(f"현재 설정된 물리적 조건(이동속도 {sec_per_floor}초, 문 개폐 {door_time}초 등)으로는 입력하신 목표 시간을 달성하기 어렵습니다.")
        st.write(f"- 총 {delayed_count}개의 동선에서 병목이 예상됩니다.")
        st.write("- 해결을 위해 '한 층 이동 시간'을 줄이거나, '문 개폐 시간' 설정을 현실적으로 조정해 보시기 바랍니다.")
    else:
        st.success("설정된 물리적 조건 내에서 모든 목표 시간 달성이 가능할 것으로 예측됩니다.")
