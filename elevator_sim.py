import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Strategic Experiment Lab")
st.caption("배치 전략, 혼잡도 로직, 군집 제어 알고리즘을 통합 분석하는 고도화 시뮬레이터입니다.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 거주 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (분석 제외)", 1, 5, 3)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=2, max_value=10)

    st.divider()

    st.header("⚡ 물리 및 가속도 설정")
    sec_per_floor = st.number_input("정속 주행 시 층당 시간(초)", value=1.0)
    accel_delay = st.number_input("가속/감속 추가 지연(초)", value=1.5)
    door_time = st.number_input("문 개폐 시간(초)", value=7.0)

    st.divider()
    
    st.header("⚠️ 최대 허용 대기 시간 설정 (초)")
    limit_1f_up = st.slider("1F → 거주층 최대치", 30, 120, 45)
    limit_1f_down = st.slider("거주층 → 1F 최대치", 30, 180, 80)
    limit_b_up = st.slider("지하 → 거주층 최대치", 30, 150, 60)
    limit_b_down = st.slider("거주층 → 지하 최대치", 30, 180, 90)

# ----------------- MAIN PANEL: SCENARIO SETTINGS -----------------
st.header("⚙️ 시나리오 및 운영 알고리즘 설정")

# 1. 운영 로직 및 혼잡도 설정
col_sc1, col_sc2 = st.columns(2)
with col_sc1:
    logic_type = st.radio(
        "🕹️ 적용할 운영 알고리즘 (군집 제어)",
        ["전 층 자유 운행 (기본)", "홀짝수층 분리 운행", "저층/고층부 분할 운행"],
        horizontal=True,
        help="단순 배치를 넘어 시스템적인 운행 제한 로직을 적용합니다."
    )
    mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], horizontal=True)

with col_sc2:
    congestion_level = st.select_slider(
        "👥 건물 혼잡도 설정", 
        options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡"], 
        value="보통"
    )
    delivery_mode = st.toggle("📦 택배 배달 지연 모드 활성화")

st.subheader("🚗 주차장(지하) 이용 비중")
c_p1, c_p2 = st.columns(2)
with c_p1: p_up_ratio = st.slider("지하에서 올라가는 비율 (%)", 0, 100, 30)
with c_p2: p_down_ratio = st.slider("지하로 내려가는 비율 (%)", 0, 100, 40)

st.divider()

# 2. 배치 방식 결정
placement_mode = st.radio("📍 대기 위치 결정 방식", ["AI 자동 최적화 배치", "사용자 수동 배치"], horizontal=True)

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

final_placements = []
if placement_mode == "사용자 수동 배치":
    st.info("각 엘리베이터의 초기 대기 위치를 직접 지정하세요.")
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            final_placements.append(val)
else:
    # AI 최적화 배치 로직
    if mode_label == "출근 시간":
        final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    elif mode_label == "퇴근 시간":
        num_b = int(num_elevators * (max(p_up_ratio, p_down_ratio) / 100))
        final_placements = [random.randint(0, idx_1f-1) for _ in range(num_b)] + [idx_1f] * (num_elevators - num_b)
    else:
        final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    
    st.success(f"🤖 AI가 '{mode_label}' 패턴을 분석하여 최적 대기 위치를 산출했습니다.")
    cols = st.columns(num_elevators)
    for i, p in enumerate(final_placements):
        cols[i].metric(f"EL {chr(65+i)} 배치", FLOOR_LABELS[p])

run_btn = st.button("🚀 통합 성능 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: ENGINE -----------------

def get_reachable_elevators(target_floor_idx, logic, num_els):
    """선택된 알고리즘에 따라 응답 가능한 엘리베이터 인덱스 반환"""
    available = []
    # 지하 포함 실질 층수 (계산용)
    actual_floor = target_floor_idx - min_f 
    
    for i in range(num_els):
        if logic == "전 층 자유 운행 (기본)":
            available.append(i)
        elif logic == "홀짝수층 분리 운행":
            # 1층(idx_1f)은 공통 응답, 그 외에는 홀짝 적용
            if target_floor_idx == idx_1f or (i % 2 == 0 and actual_floor % 2 != 0) or (i % 2 != 0 and actual_floor % 2 == 0):
                available.append(i)
        elif logic == "저층/고층부 분할 운행":
            mid = total_fs // 2
            if target_floor_idx == idx_1f or (i < num_els/2 and target_floor_idx <= mid) or (i >= num_els/2 and target_floor_idx > mid):
                available.append(i)
    return available if available else list(range(num_els))

def calculate_complex_time(start_idx, end_idx, placements, logic, cong, is_deliv):
    # 가중치 설정
    c_map = {"매우 쾌적": 0.7, "여유": 0.9, "보통": 1.1, "혼잡": 1.6, "매우 혼잡": 2.5}
    w = c_map[cong]
    
    # 응답 가능한 엘리베이터 필터링
    avail_indices = get_reachable_elevators(start_idx, logic, len(placements))
    avail_placements = [placements[i] for i in avail_indices]
    
    # 최적 응답 거리 계산
    min_dist = min([abs(f_idx - start_idx) for f_idx in avail_placements])
    
    # 물리 지연 시간 계산
    wait_t = (min_dist * sec_per_floor) + (accel_delay * w)
    move_t = (abs(start_idx - end_idx) * sec_per_floor) + (accel_delay * w)
    
    # 승하차 지연 (세대수 반영)
    h_weight = 1 + (households_per_floor * 0.05)
    loading_t = (door_time * w) * h_weight
    
    total = wait_t + move_t + loading_t
    if is_deliv: total *= 1.3
    return total

if run_btn:
    # 대조군(무작위 분산) 계산
    def get_random_avg(start, end, n, logic, cong, is_deliv):
        results = []
        for _ in range(10):
            r_pos = [random.randint(0, total_fs-1) for _ in range(n)]
            results.append(calculate_complex_time(start, end, r_pos, logic, cong, is_deliv))
        return sum(results) / 10

    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    nodes = {
        "1F ⬆️ 거주층": (idx_1f, avg_res_f, limit_1f_up),
        "거주층 ⬇️ 1F": (avg_res_f, idx_1f, limit_1f_down),
        "지하 ⬆️ 거주층": (0, avg_res_f, limit_b_up),
        "거주층 ⬇️ 지하": (avg_res_f, 0, limit_b_down)
    }

    st.subheader(f"📊 분석 결과 (알고리즘: {logic_type} / 혼잡도: {congestion_level})")
    
    # 가중치 메모용
    c_map_display = {"매우 쾌적": 0.7, "여유": 0.9, "보통": 1.1, "혼잡": 1.6, "매우 혼잡": 2.5}
    curr_w = c_map_display[congestion_level]

    m_cols = st.columns(4)
    report_list = []
    chart_data = []

    for i, (name, (start, end, limit)) in enumerate(nodes.items()):
        strategy_t = calculate_complex_time(start, end, final_placements, logic_type, congestion_level, delivery_mode)
        random_t = get_random_avg(start, end, num_elevators, logic_type, congestion_level, delivery_mode)
        
        is_exceed = strategy_t > limit
        delta_color = "normal" if not is_exceed else "inverse"

        with m_cols[i]:
            st.metric(name, f"{strategy_t:.1f}초", f"한계: {limit}초", delta_color=delta_color)
            if is_exceed: st.error(f"🚨 임계치 초과 (+{strategy_t-limit:.1f}초)")
            else: st.success("✅ 서비스 수준 통과")
        
        report_list.append({
            "노선": name,
            "전략 적용": f"{strategy_t:.1f}초",
            "무작위 분산": f"{random_t:.1f}초",
            "한계치": f"{limit}초",
            "상태": "안정" if not is_exceed else "위험"
        })
        chart_data.append({"노선": name, "현재 전략": strategy_t, "최대 허용치": limit, "무작위 분산": random_t})

    st.divider()
    
    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        st.write("#### 📈 노선별 성능 비교 차트")
        st.bar_chart(pd.DataFrame(chart_data).set_index("노선"))
    
    with col_info:
        st.write("#### 📝 운영 리포트")
        st.info(f"선택된 **{logic_type}** 알고리즘은 호출 가능한 엘리베이터 세트를 동적으로 제한하여 군집 효율을 높입니다.")
        st.write(f"- **혼잡 가중치:** {curr_w}배 적용")
        st.write(f"- **세대수 밀도:** {households_per_floor}세대/층 반영")
        if delivery_mode: st.warning("택배 지연 모드가 전체 시간에 30% 추가 지연을 발생시키고 있습니다.")

    st.write("#### 📋 상세 데이터 테이블")
    st.table(pd.DataFrame(report_list))
