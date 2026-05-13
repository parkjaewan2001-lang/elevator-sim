import streamlit as st
import random
import pandas as pd

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Ultimate Elevator Optimizer", layout="wide")

st.title("🏢 Ultimate Elevator Optimizer")
st.caption("시간대별 정밀 분석 및 물리적 지연 수치를 반영한 현실적 시뮬레이터")

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
    st.write("인당 탑승/하차 지연 시간(초)")
    delay_col1, delay_col2 = st.columns([1.5, 1])
    with delay_col1:
        preset = st.selectbox("상황 프리셋", ["직접 입력", "쾌적(0.8)", "보통(1.2)", "혼잡(2.5)"])
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

# ----------------- MAIN PANEL: SCENARIO -----------------
st.header("⚙️ 시나리오 및 비율 상세 설정")
mode_col, ratio_col = st.columns([1, 1])

with mode_col:
    # 시간대 세분화: 낮 시간과 새벽 시간 추가
    mode_label = st.radio(
        "⏰ 분석 시간대 선택", 
        ["출근 시간", "퇴근 시간", "낮 시간 (배달/방문)", "새벽 시간 (정적)"], 
        horizontal=True
    )
    mode_map = {
        "출근 시간": "morning", 
        "퇴근 시간": "evening", 
        "낮 시간 (배달/방문)": "daytime", 
        "새벽 시간 (정적)": "night"
    }
    current_mode = mode_map[mode_label]

with ratio_col:
    if current_mode == "morning":
        p_ratio = st.number_input("출근 시 주차장(지하) 하차 비율 (%)", min_value=0, max_value=100, value=40)
    elif current_mode == "evening":
        p_ratio = st.number_input("퇴근 시 주차장(지하) 승차 비율 (%)", min_value=0, max_value=100, value=30)
    elif current_mode == "daytime":
        p_ratio = st.number_input("배달/택배 지하 주차장 이용 비율 (%)", min_value=0, max_value=100, value=20)
    else:
        st.write("새벽 시간은 호출 빈도가 매우 낮으며 주차장 이동이 드뭅니다.")
        p_ratio = 10

st.divider()
run_btn = st.button("🚀 최적 배치 및 현실적 지연 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: CALCULATION -----------------
if run_btn:
    FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
    idx_1f = min_f
    total_fs = len(FLOOR_LABELS)
    
    # 1. 최적 대기층 계산 로직
    best_floors = []
    reason = ""
    
    if current_mode == "morning":
        step = (total_fs - idx_1f) // (num_elevators + 1)
        best_floors = [int(idx_1f + (step * (i+1))) for i in range(num_elevators)]
        reason = "상층부 거주민의 하행 호출이 집중되므로 엘리베이터를 상층 구역에 분산 배치했습니다."
    elif current_mode == "evening":
        num_to_b = int(num_elevators * (p_ratio / 100))
        for i in range(num_elevators):
            best_floors.append(random.randint(0, idx_1f - 1) if i < num_to_b else idx_1f)
        reason = f"로비와 지하({p_ratio}%) 승차 인원을 위해 하층부에 집중 배치했습니다."
    elif current_mode == "daytime":
        # 낮 시간: 1층(배달)과 중간층(가정 방문)에 적절히 분산
        best_floors = [idx_1f] + [int(total_fs * 0.6)] * (num_elevators - 1)
        reason = "배달원 유입이 많은 1층과 가사 방문객을 위한 중간층에 혼합 배치했습니다."
    else:
        # 새벽 시간: 에너지 절약 및 1층 복귀 위주
        best_floors = [idx_1f] * num_elevators
        reason = "호출이 드문 시간대이므로 모든 엘리베이터를 1층(메인 로비)에 대기시킵니다."

    # 2. 물리적 예상 시간 계산
    avg_high_f = idx_1f + (max_f * 0.7) # 주로 거주하는 층 (70% 높이 가정)
    
    def get_real_time(s, e):
        # (이동 시간) + (문 개폐 * 2) + (지연 * 탑승객2명 가중치)
        return (abs(s - e) * sec_per_floor) + (door_time * 2) + (boarding_delay * 4)

    est_times = {
        "1층 → 거주층": get_real_time(idx_1f, avg_high_f),
        "주차장 → 거주층": get_real_time(0, avg_high_f),
        "거주층 → 1층": get_real_time(avg_high_f, idx_1f),
        "거주층 → 주차장": get_real_time(avg_high_f, 0)
    }
    targets = [t_1f_to_res, t_b_to_res, t_res_to_1f, t_res_to_b]

    # 3. 결과 대시보드 출력
    st.subheader(f"📍 {mode_label} AI 최적 대기 위치")
    cols = st.columns(num_elevators)
    for i, f_idx in enumerate(best_floors):
        cols[i].metric(f"엘리베이터 {chr(65+i)}", FLOOR_LABELS[f_idx])
    
    st.divider()

    st.subheader("🔍 성능 분석 결과 (목표 대비 현실)")
    
    res_list = []
    for (path, est), target in zip(est_times.items(), targets):
        diff = est - target
        status = "✅ 달성" if diff <= 0 else f"⚠️ {diff:.1f}초 지연"
        res_list.append({"동선": path, "목표": f"{target}초", "예상": f"{est:.1f}초", "결과": status})
    
    st.table(pd.DataFrame(res_list))
    
    st.info(f"**최적화 근거:** {reason}")
    if any("지연" in r["결과"] for r in res_list):
        st.warning("일부 동선에서 물리적 한계로 인한 지연이 발생합니다. 목표 시간을 현실적으로 수정하거나 장비 성능 설정을 검토하세요.")
