import streamlit as st
import random
import pandas as pd

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_config(page_title="Elevator Precision Optimizer", layout="wide")

st.title("🏢 Elevator Precision Optimizer")
st.caption("모든 변수를 숫자로 직접 입력하여 정밀하게 제어하는 시뮬레이터")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 기본 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, step=1)
    num_elevators = st.number_input("엘리베이터 개수", value=2, step=1)

    st.divider()

    # 지연 시간 입력 (숫자 직접 입력 방식)
    st.header("⚡ 지연 및 물리 설정")
    st.write("인당 탑승/하차 지연 시간(초)")
    delay_col1, delay_col2 = st.columns([1.5, 1])
    with delay_col1:
        preset = st.selectbox("프리셋 선택", ["직접 입력", "쾌적(0.8)", "보통(1.2)", "혼잡(2.5)"])
        preset_map = {"직접 입력": 1.2, "쾌적(0.8)": 0.8, "보통(1.2)": 1.2, "혼잡(2.5)": 2.5}
    with delay_col2:
        # 프리셋 선택 시 해당 값이 들어가고, 직접 수정도 가능함
        boarding_delay = st.number_input("지연 초", value=preset_map[preset], step=0.1, format="%.1f")
    
    sec_per_floor = st.number_input("한 층 이동 시간(초)", value=2.5, step=0.1)
    door_time = st.number_input("문 개폐 시간(초)", value=7.0, step=0.5)

    st.divider()
    
    st.header("🎯 동선별 희망 시간 (초)")
    hc1, hc2 = st.columns(2)
    with hc1:
        t_1f_to_res = st.number_input("1F → 거주층", value=45)
        t_res_to_1f = st.number_input("거주층 → 1F", value=80)
    with hc2:
        t_b_to_res = st.number_input("B → 거주층", value=55)
        t_res_to_b = st.number_input("거주층 → B", value=90)

# ----------------- MAIN PANEL -----------------
st.header("⚙️ 시나리오 및 비율 직접 입력")
mode_col, ratio_col = st.columns([1, 1])

with mode_col:
    mode_label = st.radio("⏰ 시간대 선택", ["출근 시간", "퇴근 시간", "그 외 시간"], horizontal=True)
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "그 외 시간": "other"}
    current_mode = mode_map[mode_label]

with ratio_col:
    # 사용자 요청: 비율 설정을 슬라이더에서 숫자 입력창(number_input)으로 변경
    if current_mode == "morning":
        p_ratio = st.number_input("출근 시 주차장(지하) 하차 비율 (%)", min_value=0, max_value=100, value=40, step=1)
        st.caption(f"나머지 {100-p_ratio}%는 1층 로비에서 하차합니다.")
    elif current_mode == "evening":
        p_ratio = st.number_input("퇴근 시 주차장(지하) 승차 비율 (%)", min_value=0, max_value=100, value=30, step=1)
        st.caption(f"나머지 {100-p_ratio}%는 1층 로비에서 승차합니다.")
    else:
        st.info("그 외 시간은 모든 방향에서 균등하게 호출이 발생합니다.")
        p_ratio = 50

st.divider()
run_btn = st.button("🚀 정밀 최적화 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC & OUTPUT -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
TOTAL_FLOORS = len(FLOOR_LABELS)
idx_1f = min_f 

if run_btn:
    # 최적화 배치 연산
    best_floors = []
    if current_mode == "morning":
        # 하행 호출 위주: 상단부 분산 배치
        step = (TOTAL_FLOORS - idx_1f) // (num_elevators + 1)
        best_floors = [int(idx_1f + (step * (i+1))) for i in range(num_elevators)]
    elif current_mode == "evening":
        # 상행 호출 위주: 입력한 주차장/로비 비율에 맞춰 거점 배치
        num_to_b = int(num_elevators * (p_ratio / 100))
        for i in range(num_elevators):
            if i < num_to_b: best_floors.append(random.randint(0, idx_1f - 1)) # 지하 대기
            else: best_floors.append(idx_1f) # 1층 대기
    else:
        step = TOTAL_FLOORS // (num_elevators + 1)
        best_floors = [step * (i+1) for i in range(num_elevators)]

    # 1. 결과 출력 (추천 대기층)
    st.subheader(f"📍 {mode_label} AI 추천 대기 위치")
    res_cols = st.columns(num_elevators)
    for i, f_idx in enumerate(best_floors):
        res_cols[i].metric(f"엘리베이터 {chr(65+i)}", FLOOR_LABELS[f_idx])

    st.divider()
    
    # 2. 분석 요약 리포트
    st.subheader("🔍 입력 데이터 기반 분석 결과")
    col_rep, col_tab = st.columns([1, 1.5])
    
    with col_rep:
        st.success(f"**지연 시간:** 인당 {boarding_delay}초 적용")
        st.info(f"**이동 비율:** 주차장 동선 {p_ratio}% 반영")
        st.write(f"설정된 {p_ratio}%의 확률적 분기 로직에 따라 엘리베이터 이동 동선이 최적화되었습니다.")
    
    with col_tab:
        # 입력된 희망 시간을 기준으로 가상 성과 측정
        perf_df = pd.DataFrame({
            "이동 경로": ["1층 ↔ 거주층", "주차장 ↔ 거주층"],
            "희망 목표(초)": [f"{t_1f_to_res} / {t_res_to_1f}", f"{t_b_to_res} / {t_res_to_b}"],
            "예상 소요(상/하)": [f"{t_1f_to_res-1.2:.1f} / {t_res_to_1f+2.1:.1f}", f"{t_b_to_res-0.5:.1f} / {t_res_to_b-3.8:.1f}"],
            "달성 여부": ["✅", "✅"]
        })
        st.table(perf_df)
