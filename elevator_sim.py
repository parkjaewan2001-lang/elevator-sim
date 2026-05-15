import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")
st.caption("물리 법칙, 운영 알고리즘, 사용자 행동 및 새벽 배송 패턴이 통합된 최종 시뮬레이터입니다.")

# ----------------- SIDEBAR: 고정 환경 및 물리 설정 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 물리 기본 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=2, max_value=10)
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    
    st.divider()
    st.header("🚀 물리 엔진 설정")
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)

    st.divider()
    st.header("⚡ 문 개폐 및 행동 설정")
    base_door_time = st.number_input("기본 문 개폐 시간 (초)", value=7.0)
    button_efficiency = st.slider("🔘 닫힘 버튼 사용 효율 (%)", 0, 100, 40)
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (분석 제외)", 1, 5, 3)

    st.divider()
    st.header("⚠️ 서비스 임계치 (초)")
    limit_up = st.slider("상행 최대 허용", 30, 150, 60)
    limit_down = st.slider("하행 최대 허용", 30, 180, 80)

# ----------------- MAIN PANEL: 전략 및 시나리오 -----------------
st.header("⚙️ 시뮬레이션 전략 설정")

# [핵심] 상호 배타적 모드 제어
analysis_mode = st.radio(
    "🔬 분석 핵심 변수 선택 (모드에 따라 설정창이 상호 배타적으로 활성화됩니다)",
    ["운영 알고리즘 기반 분석 (홀짝/분할)", "대기 위치 배치 기반 분석 (AI/수동/새벽)"],
    horizontal=True
)

st.divider()
col_left, col_right = st.columns(2)

# 기초 데이터 계산
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

# 모드별 변수 초기화
logic_type = "전 층 자유 운행 (기본)"
final_placements = [idx_1f] * num_elevators
mode_label = "낮 시간"

with col_left:
    st.subheader("🕹️ 운영 알고리즘 (Software)")
    if analysis_mode == "운영 알고리즘 기반 분석 (홀짝/분할)":
        logic_type = st.selectbox("알고리즘 선택", ["홀짝수층 분리 운행", "저층/고층부 분할 운행"])
        st.success("✅ 알고리즘 모드: 대기 위치는 1F로 통제됩니다.")
    else:
        st.write("❌ **비활성화됨**")
        st.caption("배치 분석 모드에서는 '전 층 자유 운행'이 적용됩니다.")

with col_right:
    st.subheader("📍 대기 위치 배치 (Topology)")
    if analysis_mode == "대기 위치 배치 기반 분석 (AI/수동/새벽)":
        placement_method = st.radio("결정 방식", ["AI 자동 최적화", "사용자 수동 배치"], horizontal=True)
        mode_label = st.select_slider("시간대 패턴", options=["새벽 시간", "출근 시간", "낮 시간", "퇴근 시간"], value="낮 시간")
        
        if placement_method == "사용자 수동 배치":
            final_placements = []
            m_cols = st.columns(num_elevators)
            for i in range(num_elevators):
                with m_cols[i]:
                    val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
                    final_placements.append(val)
        else:
            # AI 배치 로직 (새벽 시간 포함)
            if mode_label == "새벽 시간":
                final_placements = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2)
            elif mode_label == "출근 시간":
                final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
            elif mode_label == "퇴근 시간":
                final_placements = [idx_1f] * num_elevators
            else:
                final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
            
            p_cols = st.columns(num_elevators)
            for i, p in enumerate(final_placements):
                p_cols[i].metric(f"EL {chr(65+i)}", FLOOR_LABELS[p])
    else:
        st.write("❌ **비활성화됨**")
        st.caption("알고리즘 모드에서는 모든 기기가 1층에서 대기합니다.")

st.divider()
st.subheader("🌐 환경 변수 통합 설정")
c_env1, c_env2, c_env3 = st.columns(3)
with c_env1: 
    congestion = st.select_slider("건물 혼잡도", options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡"], value="보통")
with c_env2: 
    delivery = st.toggle("📦 택배/새벽 배송 지연 모드", value=True if mode_label == "새벽 시간" else False)
with c_env3: 
    dynamic_door = st.toggle("🚪 동적 문 개폐 로직 적용", value=True)

# ----------------- LOGIC: PHYSICS & ALGORITHM ENGINE -----------------

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

def calculate_final_time(start, end, placements, logic, cong, is_deliv, eff, door_active):
    c_map = {"매우 쾌적": 0.7, "여유": 0.8, "보통": 1.1, "혼잡": 1.6, "매우 혼잡": 2.5}
    w = c_map[cong]
    
    # 응답 가능 엘리베이터 필터링
    avail = get_reachable_elevators(start, logic, len(placements), idx_1f, total_fs)
    min_dist_m = min([abs(placements[i] - start) for i in avail]) * floor_height
    
    # 물리 엔진: 대기/이동 시간
    wait_t = get_travel_time(min_dist_m, max_velocity, acceleration)
    move_t = get_travel_time(abs(start - end) * floor_height, max_velocity, acceleration)
    
    # 동적 문 개폐: 탑승객 유무(In-car/Out-of-car) 및 닫힘 버튼 반영
    is_inside = True if start > idx_1f else False
    if door_active and is_inside:
        door_t = base_door_time * (1 - (eff/100))
    else:
        door_t = base_door_time * 1.2 # 하차 후 자동 닫힘 지연
    
    # 가중치 결합 (밀도, 혼잡도)
    loading_t = (door_t * w) * (1 + (households_per_floor * 0.05))
    total = (wait_t + move_t + loading_t)
    
    # 배송 모드 가중치
    if is_deliv: total *= 1.4 if mode_label == "새벽 시간" else 1.3
    return total, door_t

# ----------------- EXECUTION -----------------
if st.button("🚀 통합 시뮬레이션 실행", type="primary", use_container_width=True):
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.7)
    scenarios = {
        "1F ⬆️ 거주층 (상행)": (idx_1f, avg_res_f, limit_up),
        "거주층 ⬇️ 1F (하행)": (avg_res_f, idx_1f, limit_down)
    }

    st.subheader(f"📊 분석 결과 리포트 (모드: {analysis_mode})")
    m_cols = st.columns(2)
    chart_data = []

    for i, (name, (start, end, limit)) in enumerate(scenarios.items()):
        strategy_t, door_t = calculate_final_time(start, end, final_placements, logic_type, congestion, delivery, button_efficiency, dynamic_door)
        
        # 무작위 분산 대조군 (10회 평균)
        rand_t = sum([calculate_final_time(start, end, [random.randint(0, total_fs-1) for _ in range(num_elevators)], logic_type, congestion, delivery, button_efficiency, dynamic_door)[0] for _ in range(10)]) / 10
        
        is_exceed = strategy_t > limit
        with m_cols[i]:
            st.metric(name, f"{strategy_t:.1f}초", f"대조군 대비 {strategy_t-rand_t:+.1f}초", delta_color="normal" if strategy_t < rand_t else "inverse")
            if is_exceed: st.error(f"🚨 임계치({limit}s) 초과!")
            else: st.success("✅ 서비스 수준 만족")
        
        chart_data.append({"노선": name, "현재 전략": strategy_t, "무작위 대조군": rand_t, "임계치": limit})

    st.divider()
    c_graph, c_info = st.columns([2, 1])
    with c_graph:
        st.bar_chart(pd.DataFrame(chart_data).set_index("노선"))
    with c_info:
        st.write("#### 📝 시뮬레이션 요약")
        st.info(f"선택 패턴: {mode_label}\n운영 알고리즘: {logic_type}")
        st.write(f"- 물리엔진: {max_velocity}m/s, {acceleration}m/s²")
        st.write(f"- 문 개폐: {door_t:.1f}s (동적 로직 적용)")
        if delivery: st.warning("⚠️ 배송 지연 가중치 적용 중")
