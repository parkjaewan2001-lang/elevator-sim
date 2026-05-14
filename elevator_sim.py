import streamlit as st
import random
import pandas as pd

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("AI 최적화 추천과 사용자 수동 배치를 자유롭게 실험하고 성능을 비교하세요.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 기본 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, step=1)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10, step=1)

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

# ----------------- MAIN PANEL: SCENARIO & PLACEMENT -----------------
st.header("⚙️ 시뮬레이션 설정")
mode_col, placement_col = st.columns([1, 1])

with mode_col:
    mode_label = st.radio(
        "⏰ 분석 시간대 선택", 
        ["출근 시간", "퇴근 시간", "낮 시간 (배달/방문)", "새벽 시간 (정적)"], 
        horizontal=True
    )
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "낮 시간 (배달/방문)": "daytime", "새벽 시간 (정적)": "night"}
    current_mode = mode_map[mode_label]

with placement_col:
    placement_method = st.radio("📍 배치 방식 선택", ["AI 자동 최적화 추천", "사용자 수동 배치 입역"], horizontal=True)

# 층 레이블 생성
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

# 수동 배치 입력창
manual_floors = []
if "수동 배치" in placement_method:
    st.info("각 엘리베이터가 대기할 고정 층수를 직접 선택하세요.")
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"엘리베이터 {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            manual_floors.append(val)

st.divider()
st.subheader("📊 세부 동선 비율 설정 (%)")
r_c1, r_c2 = st.columns(2)
with r_c1:
    if current_mode == "morning":
        p_ratio = st.number_input("출근 시 주차장(지하) 하차 비율", value=40)
    elif current_mode == "evening":
        p_ratio = st.number_input("퇴근 시 주차장(지하) 승차 비율", value=30)
    elif current_mode == "daytime":
        p_ratio = st.number_input("낮 시간 주차장 이용 비율", value=20)
    else:
        p_ratio = 10
with r_c2:
    st.write("") 
    st.caption(f"나머지 {100-p_ratio}%는 1층 로비 동선으로 계산됩니다.")

run_btn = st.button("🚀 시뮬레이션 및 현실적 성능 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: CALCULATION -----------------
if run_btn:
    # 1. 배치 결정
    best_floors = []
    if "AI" in placement_method:
        if current_mode == "morning":
            step = (total_fs - idx_1f) // (num_elevators + 1)
            best_floors = [int(idx_1f + (step * (i+1))) for i in range(num_elevators)]
        elif current_mode == "evening":
            num_to_b = int(num_elevators * (p_ratio / 100))
            for i in range(num_elevators):
                best_floors.append(random.randint(0, idx_1f - 1) if i < num_to_b else idx_1f)
        elif current_mode == "daytime":
            best_floors = [idx_1f] + [int(total_fs * 0.6)] * (max(0, num_elevators - 1))
        else:
            best_floors = [idx_1f] * num_elevators
    else:
        best_floors = manual_floors

    # 2. 결과 출력 (대기 위치)
    st.subheader(f"📍 적용된 대기 위치 ({placement_method})")
    cols = st.columns(num_elevators)
    for i, f_idx in enumerate(best_floors):
        cols[i].metric(f"엘리베이터 {chr(65+i)}", FLOOR_LABELS[f_idx])

    st.divider()

    # 3. 현실적 응답 시간 계산
    avg_high_f = idx_1f + (max_f * 0.7) 
    
    def get_realistic_response(target_start_idx, target_end_idx, current_placements):
        dist_to_call = min([abs(f_idx - target_start_idx) for f_idx in current_placements])
        travel_dist = abs(target_start_idx - target_end_idx)
        return ((dist_to_call + travel_dist) * sec_per_floor) + (door_time * 2) + (boarding_delay * 4)

    est_times = {
        "1층 → 거주층": get_realistic_response(idx_1f, avg_high_f, best_floors),
        "주차장 → 거주층": get_realistic_response(0, avg_high_f, best_floors),
        "거주층 → 1층": get_realistic_response(avg_high_f, idx_1f, best_floors),
        "거주층 → 주차장": get_realistic_response(avg_high_f, 0, best_floors)
    }
    targets = [t_1f_to_res, t_b_to_res, t_res_to_1f, t_res_to_b]

    # 4. 결과 리포트
    st.subheader("🔍 현실적 성능 분석 결과")
    res_list = []
    for (path, est), target in zip(est_times.items(), targets):
        diff = est - target
        status = "✅ 달성" if diff <= 0 else f"⚠️ {diff:.1f}초 지연"
        res_list.append({"동선": path, "목표": f"{target}초", "예상": f"{est:.1f}초", "상태": status})
    
    st.table(pd.DataFrame(res_list))
    
    if any("지연" in r["상태"] for r in res_list):
        st.error("현재 배치에서는 물리적 한계로 인해 목표 시간 달성이 어렵습니다.")
    else:
        st.success("축하합니다! 모든 동선에서 목표 시간을 만족하는 효율적인 배치입니다.")    st.header("🎯 동선별 희망 목표 시간 (초)")
    hc1, hc2 = st.columns(2)
    with hc1:
        t_1f_to_res = st.number_input("1F → 거주층", value=45)
        t_res_to_1f = st.number_input("거주층 → 1F", value=80)
    with hc2:
        t_b_to_res = st.number_input("B → 거주층", value=55)
        t_res_to_b = st.number_input("거주층 → B", value=90)

# ----------------- MAIN PANEL: SCENARIO & PLACEMENT -----------------
st.header("⚙️ 시뮬레이션 설정")
mode_col, placement_col = st.columns([1, 1])

with mode_col:
    mode_label = st.radio(
        "⏰ 분석 시간대 선택", 
        ["출근 시간", "퇴근 시간", "낮 시간 (배달/방문)", "새벽 시간 (정적)"], 
        horizontal=True
    )
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "낮 시간 (배달/방문)": "daytime", "새벽 시간 (정적)": "night"}
    current_mode = mode_map[mode_label]

with placement_col:
    placement_method = st.radio("📍 배치 방식 선택", ["AI 자동 최적화 추천", "사용자 수동 배치"], horizontal=True)

# 층 레이블 생성
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

# [신규] 수동 배치 입력창
manual_floors = []
if placement_method == "사용자 수동 배치":
    st.info("각 엘리베이터가 대기할 층을 직접 입력하세요.")
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"엘리베이터 {chr(65+i)} 대기층", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            manual_floors.append(val)

# 세부 비율 설정 (숫자 입력 유지)
st.divider()
st.subheader("📊 세부 동선 비율 설정 (%)")
r_c1, r_c2 = st.columns(2)
with r_c1:
    if current_mode == "morning":
        p_ratio = st.number_input("출근 시 주차장(지하) 하차 비율", value=40)
    elif current_mode == "evening":
        p_ratio = st.number_input("퇴근 시 주차장(지하) 승차 비율", value=30)
    elif current_mode == "daytime":
        p_ratio = st.number_input("낮 시간 주차장 이용 비율", value=20)
    else:
        p_ratio = 10
with r_c2:
    st.write("") # 간격 맞춤
    st.caption(f"나머지 {100-p_ratio}%는 1층 로비(메인 입구) 동선으로 계산됩니다.")

run_btn = st.button("🚀 시뮬레이션 및 성능 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: CALCULATION -----------------
if run_btn:
    # 1. 배치 결정
    best_floors = []
    if placement_method == "AI 자동 최적화 추천":
        if current_mode == "morning":
            step = (total_fs - idx_1f) // (num_elevators + 1)
            best_floors = [int(idx_1f + (step * (i+1))) for i in range(num_elevators)]
        elif current_mode == "evening":
            num_to_b = int(num_elevators * (p_ratio / 100))
            for i in range(num_elevators):
                best_floors.append(random.randint(0, idx_1f - 1) if i < num_to_b else idx_1f)
        elif current_mode == "daytime":
            best_floors = [idx_1f] + [int(total_fs * 0.6)] * (num_elevators - 1)
        else:
            best_floors = [idx_1f] * num_elevators
    else:
        best_floors = manual_floors

    # 2. 결과 출력 (대기 위치)
    st.subheader(f"📍 적용된 대기 위치 ({placement_method})")
    cols = st.columns(num_elevators)
    for i, f_idx in enumerate(best_floors):
        cols[i].metric(f"엘리베이터 {chr(65+i)}", FLOOR_LABELS[f_idx])

    st.divider()

    # 3. 물리적 예상 시간 계산 (가장 가까운 엘리베이터의 응답 시간 반영)
    avg_high_f = idx_1f + (max_f * 0.7) 
    
    def get_realistic_response(target_start_idx, target_end_idx, current_placements):
        # 호출지까지 가장 가까운 엘리베이터가 이동하는 시간 계산
        dist_to_call = min([abs(f_idx - target_start_idx) for f_idx in current_placements])
        travel_dist = abs(target_start_idx - target_end_idx)
        
        # 총 시간 = (대기지->호출지 이동) + (호출지->목적지 이동) + 문개폐*2 + 지연*4
        total_time = ((dist_to_call + travel_dist) * sec_per_floor) + (door_time * 2) + (boarding_delay * 4)
        return total_time

    est_times = {
        "1층 → 거주층": get_realistic_response(idx_1f, avg_high_f, best_floors),
        "주차장 → 거주층": get_realistic_response(0, avg_high_f, best_floors),
        "거주층 → 1층": get_realistic_response(avg_high_f, idx_1f, best_floors),
        "거주층 → 주차장": get_realistic_response(avg_high_f, 0, best_floors)
    }
    targets = [t_1f_to_res, t_b_to_res, t_res_to_1f, t_res_to_b]

    # 4. 성능 분석 표
    st.subheader("🔍 현실적 성능 분석 결과")
    res_list = []
    for (path, est), target in zip(est_times.items(), targets):
        diff = est - target
        status = "✅ 달성" if diff <= 0 else f"⚠️ {diff:.1f}초 지연"
        res_list.append({"동선": path, "설정 목표": f"{target}초", "물리적 예상": f"{est:.1f}초", "최종 상태": status})
    
    st.table(pd.DataFrame(res_list))
    
    # 분석 코멘트
    if any("지연" in r["최종 상태"] for r in res_list):
        st.error("현재 배치 설정으로는 물리적인 목표 달성이 어렵습니다. 대기 층수를 조정하거나 물리 설정을 변경해 보세요.")
    else:
        st.success("축하합니다! 현재 배치는 모든 동선의 목표 시간을 만족하는 효율적인 구성입니다.")토하세요.")
