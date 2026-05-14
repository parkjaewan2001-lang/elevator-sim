import streamlit as st
import pandas as pd
import numpy as np

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("엘리베이터 대수별 효율 차이와 AI 최적화 알고리즘의 성능 이득을 직관적으로 비교합니다.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 거주 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수", 1, 5, 3)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10)

    st.divider()

    st.header("⚡ 물리 및 가속도 설정")
    sec_per_floor = st.number_input("정속 주행 시 층당 시간(초)", value=1.0)
    accel_delay = st.number_input("가속/감속 추가 지연(초)", value=1.5)
    door_time = st.number_input("문 개폐 시간(초)", value=7.0)

    st.divider()
    
    st.header("🎯 목표 시간(초)")
    target_1f_up = st.number_input("1F → 거주층 목표", value=45)
    target_1f_down = st.number_input("거주층 → 1F 목표", value=80)

# ----------------- MAIN PANEL -----------------
st.header("⚙️ 시뮬레이션 설정")

col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    congestion_level = st.select_slider(
        "👥 건물 혼잡도",
        options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡"],
        value="보통"
    )
with col_cfg2:
    delivery_mode = st.toggle("📦 택배 배달 지연 모드 활성화")

# 혼잡도 및 수요 가중치 계산
congestion_map = {"매우 쾌적": 0.8, "여유": 1.0, "보통": 1.2, "혼잡": 2.0, "매우 혼잡": 3.5}
adj_delay = congestion_map[congestion_level]
household_weight = 1 + (households_per_floor * 0.03) # 세대수 비례 가중치

st.divider()

# 배치 방식 선택
placement_method = st.radio(
    "📍 알고리즘 적용 여부 선택", 
    ["자율주행 최적화 (AI 추천 배치)", "기본 고정 배치 (전체 1F 대기)"], 
    horizontal=True
)

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

run_btn = st.button("🚀 알고리즘 성능 비교 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: IMPROVED PERFORMANCE ENGINE -----------------

def get_wait_distance(start_idx, placements, is_optimized):
    """
    엘리베이터 대수에 따른 현실적 대기 거리 계산
    - 최적화 시: 가장 가까운 EL 거리 사용
    - 비최적화 시: 대수가 늘어나면 확률적으로 응답 속도가 빨라지는 '군집 효과' 반영
    """
    if is_optimized:
        return min([abs(f_idx - start_idx) for f_idx in placements])
    else:
        # 비최적화(1층 대기) 상황이라도 대수가 많으면 
        # 도어 개폐 대기나 선행 호출 처리 등으로 인해 약 15%씩 효율이 상승한다고 가정
        base_dist = abs(placements[0] - start_idx)
        efficiency_gain = (1 - (0.15 * (len(placements) - 1))) 
        return base_dist * max(0.4, efficiency_gain)

def calculate_total_time(start_idx, end_idx, placements, is_optimized):
    dist_to_call = get_wait_distance(start_idx, placements, is_optimized)
    wait_time = (dist_to_call * sec_per_floor) + accel_delay
    
    move_dist = abs(start_idx - end_idx)
    move_time = (move_dist * sec_per_floor) + accel_delay
    
    # 총 소요 시간 (가중치 포함)
    total = (wait_time + move_time + (door_time * 2) + (1.2 * 4 * adj_delay)) * household_weight
    if delivery_mode: total *= 1.3 # 택배 모드 시 30% 지연
    return total

if run_btn:
    # 1. 배치 설정
    # 최적화 배치 (층별 균등 분산)
    optimized_floors = [int(np.percentile(range(total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    # 비최적화 배치 (모두 1층)
    basic_floors = [idx_1f] * num_elevators
    
    current_floors = optimized_floors if placement_method == "자율주행 최적화 (AI 추천 배치)" else basic_floors

    # 2. 성능 계산
    avg_res_floor = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    
    # [A] 현재 선택된 방식의 시간
    time_up = calculate_total_time(idx_1f, avg_res_floor, current_floors, "AI" in placement_method)
    time_down = calculate_total_time(avg_res_floor, idx_1f, current_floors, "AI" in placement_method)
    
    # [B] 반대 방식의 시간 (비교용)
    alt_floors = basic_floors if "AI" in placement_method else optimized_floors
    alt_up = calculate_total_time(idx_1f, avg_res_floor, alt_floors, "AI" not in placement_method)
    alt_down = calculate_total_time(avg_res_floor, idx_1f, alt_floors, "AI" not in placement_method)

    # 3. 직관적 시각화 (Metric)
    st.subheader("📊 알고리즘 도입 성과 비교")
    
    m1, m2 = st.columns(2)
    
    # 상행 비교
    diff_up = time_up - alt_up
    label_up = "기본 배치 대비" if "AI" in placement_method else "AI 최적화 대비"
    m1.metric("상행 (1F → 거주층)", f"{time_up:.1f}초", f"{diff_up:+.1f}초 ({label_up})", delta_color="inverse")
    
    # 하행 비교
    diff_down = time_down - alt_down
    label_down = "기본 배치 대비" if "AI" in placement_method else "AI 최적화 대비"
    m2.metric("하행 (거주층 → 1F)", f"{time_down:.1f}초", f"{diff_down:+.1f}초 ({label_down})", delta_color="inverse")

    # 4. 상세 위치 및 효과 리포트
    st.divider()
    c_pos, c_chart = st.columns([1, 1.5])
    
    with c_pos:
        st.write("#### 📍 적용된 엘리베이터 위치")
        for i, f in enumerate(current_floors):
            st.write(f"**EL {chr(65+i)}**: {FLOOR_LABELS[f]} 대기 중")
            
    with c_chart:
        st.write("#### 📈 대수 증가에 따른 효율 개선 (추세)")
        # 대수별 시간 변화 시뮬레이션 데이터 생성
        mock_data = []
        for n in range(1, 11):
            opt_fs = [int(f) for f in np.linspace(0, total_fs-1, n)]
            bas_fs = [idx_1f] * n
            t_opt = calculate_total_time(avg_res_floor, idx_1f, opt_fs, True)
            t_bas = calculate_total_time(avg_res_floor, idx_1f, bas_fs, False)
            mock_data.append({"대수": n, "AI 최적화": t_opt, "기본 고정": t_bas})
        
        st.line_chart(pd.DataFrame(mock_data).set_index("대수"))
        st.caption("엘리베이터 대수가 늘어날수록 AI 최적화와 기본 배치의 성능 격차가 커집니다.")

    # 5. 상세 결과 테이블
    st.write("#### 📋 노선별 상세 분석")
    final_df = pd.DataFrame({
        "구분": ["상행 (1F→거주)", "하행 (거주→1F)"],
        "선택한 방식": [f"{time_up:.1f}초", f"{time_down:.1f}초"],
        "반대 방식": [f"{alt_up:.1f}초", f"{alt_down:.1f}초"],
        "효과/손실": [f"{abs(diff_up):.1f}초 절약" if diff_up < 0 else f"{diff_up:.1f}초 지연",
                   f"{abs(diff_down):.1f}초 절약" if diff_down < 0 else f"{diff_down:.1f}초 지연"]
    })
    st.table(final_df)
