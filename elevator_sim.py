import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")
st.caption("모든 물리적, 운영적, 행동적 변수를 통합한 최종 시뮬레이터입니다.")

# ----------------- SIDEBAR: 물리 및 건물 설정 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 물리 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=2, max_value=10)
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)

    st.divider()
    st.header("⚡ 문 개폐 및 행동 설정")
    base_door_time = st.number_input("기본 문 개폐 시간 (초)", value=7.0)
    button_efficiency = st.slider("🔘 닫힘 버튼 사용 효율 (%)", 0, 100, 40)
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (분석 제외)", 1, 5, 3)

    st.divider()
    st.header("⚠️ 최대 허용 대기 시간 (초)")
    limit_1f_up = st.slider("1F → 거주층 최대치", 30, 150, 60)
    limit_1f_down = st.slider("거주층 → 1F 최대치", 30, 180, 80)
    limit_b_up = st.slider("지하 → 거주층 최대치", 30, 150, 70)
    limit_b_down = st.slider("거주층 → 지하 최대치", 30, 180, 90)

# ----------------- MAIN PANEL: 로직 및 시나리오 -----------------
st.header("⚙️ 시뮬레이션 제어 센터")

# [핵심] 상호 배타적 모드 선택
analysis_mode = st.radio(
    "🔬 분석 핵심 변수 선택 (모드에 따라 설정창이 활성화/비활성화됩니다)",
    ["운영 알고리즘 기반 분석 (홀짝/분할)", "대기 위치 배치 기반 분석 (AI/수동)"],
    horizontal=True
)

st.divider()
col_left, col_right = st.columns(2)

# 층 레이블 생성용
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

# 변수 초기화
logic_type = "전 층 자유 운행 (기본)"
final_placements = [idx_1f] * num_elevators
mode_label = "평시"

with col_left:
    st.subheader("🕹️ 운영 알고리즘 (Software)")
    if analysis_mode == "운영 알고리즘 기반 분석 (홀짝/분할)":
        logic_type = st.selectbox("알고리즘 선택", ["홀짝수층 분리 운행", "저층/고층부 분할 운행"])
        st.success("✅ 알고리즘 모드 활성화 (대기 위치는 1F 고정)")
    else:
        st.write("❌ **비활성화됨**")
        st.caption("배치 분석 모드에서는 '전 층 자유 운행'이 기본 적용됩니다.")

with col_right:
    st.subheader("📍 대기 위치 배치 (Topology)")
    if analysis_mode == "대기 위치 배치 기반 분석 (AI/수동)":
        placement_method = st.radio("결정 방식", ["AI 자동 최적화", "사용자 수동 배치"], horizontal=True)
        mode_label = st.select_slider("시간대 패턴", options=["출근 시간", "낮 시간", "퇴근 시간"], value="낮 시간")
        
        if placement_method == "사용자 수동 배치":
            final_placements = []
            m_cols = st.columns(num_elevators)
            for i in range(num_elevators):
                with m_cols[i]:
                    val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
                    final_placements.append(val)
        else:
            # AI 배치 로직 (시간대 반영)
            if mode_label == "출근 시간":
                final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
            elif mode_label == "퇴근 시간":
                final_placements = [random.randint(0, idx_1f-1) for _ in range(num_elevators//2)] + [idx_1f]*(num_elevators - num_elevators//2)
            else:
                final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
            
            p_cols = st.columns(num_elevators)
            for i, p in enumerate(final_placements):
                p_cols[i].metric(f"EL {chr(65+i)}", FLOOR_LABELS[p])
    else:
        st.write("❌ **비활성화됨**")
        st.caption("알고리즘 모드에서는 모든 엘리베이터가 1층에서 대기합니다.")

st.divider()
st.subheader("🌐 공통 환경 변수")
c_env1, c_env2, c_env3 = st.columns(3)
with c_env1: congestion = st.select_slider("건물 혼잡도", options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡"], value="보통")
with c_env2: delivery = st.toggle("📦 택배 지연 모드")
with c_env3: dynamic_door = st.toggle("🚪 동적 문 개폐 적용", value=True)

# ----------------- LOGIC: PHYSICS & CALCULATION -----------------

def get_travel_time(distance_m, v_max, a):
    if distance_m <= 0: return 0
    d_accel = (v_max**2) / (2*a)
    if distance_m >= 2*d_accel:
        return (2*(v_max/a)) + (distance_m - 2*d_accel)/v_max
    return 2 * np.sqrt(distance_m/a)

def get_reachable_elevators(target_idx, logic, num_els, min_f_idx, total_fs_cnt):
    available = []
    actual_floor = target_idx - min_f_idx
    for i in range(num_els):
        if logic == "전 층 자유 운행 (기본)": available.append(i)
        elif logic == "홀짝수층 분리 운행":
            if target_idx == min_f_idx or (i%2 == 0 and actual_floor%2 != 0) or (i%2 != 0 and actual_floor%2 == 0): available.append(i)
        elif logic == "저층/고층부 분할 운행":
            mid = total_fs_cnt // 2
            if target_idx == min_f_idx or (i < num_els/2 and target_idx <= mid) or (i >= num_els/2 and target_idx > mid): available.append(i)
    return available if available else list(range(num_els))

def calculate_master_time(start, end, placements, logic, cong, is_deliv, eff, door_active):
    c_map = {"매우 쾌적": 0.7, "여유": 0.9, "보통": 1.1, "혼잡": 1.6, "매우 혼잡": 2.5}
    w = c_map[cong]
    
    # 응답 가능 엘리베이터 필터링
    avail = get_reachable_elevators(start, logic, len(placements), idx_1f, total_fs)
    avail_pos = [placements[i] for i in avail]
    min_dist_m = min([abs(p - start) for p in avail_pos]) * floor_height
    
    # 물리 이동 시간
    wait_t = get_travel_time(min_dist_m, max_velocity, acceleration)
    move_t = get_travel_time(abs(start - end) * floor_height, max_velocity, acceleration)
    
    # 동적 문 개폐 (하행/탑승 시 닫힘 버튼 적용)
    is_inside = True if start > idx_1f else False
    if door_active and is_inside:
        door_t = base_door_time * (1 - (eff/100))
    else:
        door_t = base_door_time * 1.2
    
    h_weight = 1 + (households_per_floor * 0.05)
    total = (wait_t + move_t + (door_t * w)) * h_weight
    if is_deliv: total *= 1.3
    return total, door_t

# ----------------- EXECUTION & RESULTS -----------------
if st.button("🚀 통합 시뮬레이션 분석 실행", type="primary", use_container_width=True):
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.7)
    nodes = {
        "1F ⬆️ 거주층": (idx_1f, avg_res_f, limit_1f_up),
        "거주층 ⬇️ 1F": (avg_res_f, idx_1f, limit_1f_down),
        "지하 ⬆️ 거주층": (0, avg_res_f, limit_b_up),
        "거주층 ⬇️ 지하": (avg_res_f, 0, limit_b_down)
    }

    st.subheader(f"📊 분석 결과 (모드: {analysis_mode})")
    m_cols = st.columns(4)
    report_data, chart_data = [], []

    for i, (name, (start, end, limit)) in enumerate(nodes.items()):
        strategy_t, door_t = calculate_master_time(start, end, final_placements, logic_type, congestion, delivery, button_efficiency, dynamic_door)
        
        # 무작위 대조군 (10회 평균)
        rand_results = [calculate_master_time(start, end, [random.randint(0, total_fs-1) for _ in range(num_elevators)], logic_type, congestion, delivery, button_efficiency, dynamic_door)[0] for _ in range(10)]
        random_t = sum(rand_results) / 10
        
        is_exceed = strategy_t > limit
        with m_cols[i]:
            st.metric(name, f"{strategy_t:.1f}초", f"한계: {limit}초", delta_color="normal" if not is_exceed else "inverse")
            if is_exceed: st.error("🚨 임계치 초과")
            else: st.success("✅ 안정권")
        
        report_data.append({"노선": name, "소요시간": f"{strategy_t:.1f}초", "문 개폐": f"{door_t:.1f}초", "무작위 대비": f"{strategy_t-random_t:+.1f}초", "상태": "안정" if not is_exceed else "위험"})
        chart_data.append({"노선": name, "현재 전략": strategy_t, "최대 허용치": limit, "무작위 분산": random_t})

    st.divider()
    c_left, c_right = st.columns([2, 1])
    with c_left:
        st.write("#### 📈 성능 비교 그래프")
        st.bar_chart(pd.DataFrame(chart_data).set_index("노선"))
    with c_right:
        st.write("#### 📝 물리/행동 분석 메모")
        st.info(f"운영 로직: {logic_type}\n\n혼잡 가중치: {congestion}\n\n문 효율: {button_efficiency}%")
        st.write(f"- 최고 속도: {max_velocity}m/s\n- 가속도: {acceleration}m/s²")

    st.table(pd.DataFrame(report_data))
