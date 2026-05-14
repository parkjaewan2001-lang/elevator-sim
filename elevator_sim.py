import streamlit as st
import pandas as pd

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("목표 시간 대비 실제 성능(단축/초과)을 정밀하게 분석합니다.")

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
    boarding_delay = st.number_input("인당 승하차 지연(초)", value=1.2, step=0.1)

    st.divider()
    
    st.header("🎯 동선별 목표 시간(초)")
    target_up = st.number_input("1F → 거주층 목표", value=45)
    target_down = st.number_input("거주층 → 1F 목표", value=80)

# ----------------- MAIN PANEL -----------------
st.header("⚙️ 시뮬레이션 설정")
mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], horizontal=True)
mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "낮 시간": "daytime", "새벽 시간": "night"}
current_mode = mode_map[mode_label]

placement_method = st.radio("📍 배치 방식", ["자동 최적화 추천", "사용자 수동 배치"], horizontal=True)

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

manual_floors = []
if placement_method == "사용자 수동 배치":
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            manual_floors.append(val)

run_btn = st.button("🚀 정밀 성능 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: PHYSICS ENGINE -----------------
def calc_travel_time(dist):
    if dist <= 0: return 0
    return (dist * sec_per_floor) + accel_delay

if run_btn:
    # 1. 배치 결정
    if placement_method == "자동 최적화 추천":
        if current_mode == "morning":
            step = (total_fs - idx_1f) // (num_elevators + 1)
            best_floors = [int(idx_1f + (step * (i+1))) for i in range(num_elevators)]
        elif current_mode == "evening":
            best_floors = [idx_1f] * num_elevators
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

    # 3. 성능 계산 로직
    avg_high_f = idx_1f + (max_f * 0.6) 
    
    def analyze_performance(start_f, end_f, target, placements):
        # 대기 시간: 가장 가까운 EL이 이동하는 거리
        min_dist = min([abs(f_idx - start_f) for f_idx in placements])
        wait_time = calc_travel_time(min_dist)
        
        # 이동 시간
        move_time = calc_travel_time(abs(start_f - end_f))
        
        # 총 시간
        total = wait_time + move_time + (door_time * 2) + (boarding_delay * 4)
        diff = total - target
        return total, diff

    res_up_time, res_up_diff = analyze_performance(idx_1f, avg_high_f, target_up, best_floors)
    res_down_time, res_down_diff = analyze_performance(avg_high_f, idx_1f, target_down, best_floors)

    # 4. 결과 리포트 (단축/오바 표시)
    st.divider()
    st.subheader("🔍 목표 대비 성능 분석 리포트")
    
    col_up, col_down = st.columns(2)
    
    with col_up:
        st.write("### ⬆️ 상행 (1F → 거주층)")
        st.metric("예상 소요 시간", f"{res_up_time:.1f}초", f"{res_up_diff:+.1f}초", delta_color="inverse")
        if res_up_diff <= 0:
            st.success(f"목표보다 {abs(res_up_diff):.1f}초 단축되었습니다!")
        else:
            st.error(f"목표보다 {res_up_diff:.1f}초 초과되었습니다.")

    with col_down:
        st.write("### ⬇️ 하행 (거주층 → 1F)")
        st.metric("예상 소요 시간", f"{res_down_time:.1f}초", f"{res_down_diff:+.1f}초", delta_color="inverse")
        if res_down_diff <= 0:
            st.success(f"목표보다 {abs(res_down_diff):.1f}초 단축되었습니다!")
        else:
            st.error(f"목표보다 {res_down_diff:.1f}초 초과되었습니다.")

    # 상세 비교 테이블
    st.write("#### 📋 상세 데이터")
    df_res = pd.DataFrame({
        "구분": ["상행 (1F→거주)", "하행 (거주→1F)"],
        "목표 시간": [f"{target_up}초", f"{target_down}초"],
        "예상 시간": [f"{res_up_time:.1f}초", f"{res_down_time:.1f}초"],
        "결과": [f"{abs(res_up_diff):.1f}초 단축" if res_up_diff < 0 else f"{res_up_diff:.1f}초 초과",
               f"{abs(res_down_diff):.1f}초 단축" if res_down_diff < 0 else f"{res_down_diff:.1f}초 초과"]
    })
    st.table(df_res)
