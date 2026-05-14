import streamlit as st
import pandas as pd

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("지하 주차장 동선 비율 설정 및 전 노선 목표 대비 성능 분석을 제공합니다.")

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
    target_1f_up = st.number_input("1F → 거주층 목표", value=45)
    target_1f_down = st.number_input("거주층 → 1F 목표", value=80)
    target_b_up = st.number_input("지하 → 거주층 목표", value=55)
    target_b_down = st.number_input("거주층 → 지하 목표", value=90)

# ----------------- MAIN PANEL -----------------
st.header("⚙️ 시뮬레이션 설정")
mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], horizontal=True)
mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "낮 시간": "daytime", "새벽 시간": "night"}
current_mode = mode_map[mode_label]

placement_method = st.radio("📍 배치 방식", ["자동 최적화 추천", "사용자 수동 배치"], horizontal=True)

# 층 설정
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

# [기능 복구] 주차장 이용 비율 설정
st.divider()
st.subheader("📊 주차장(지하) 이용 비중 설정 (%)")
p_ratio = st.slider("전체 이용객 중 주차장(지하층) 이용객 비율", 0, 100, 30)
st.caption(f"현재 설정: 지하층 동선 {p_ratio}% / 지상 1층 로비 동선 {100-p_ratio}%")

# 수동 배치 입력
manual_floors = []
if placement_method == "사용자 수동 배치":
    st.info("각 엘리베이터의 대기 층수를 선택하세요.")
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            manual_floors.append(val)

run_btn = st.button("🚀 전체 노선 성능 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: PHYSICS ENGINE -----------------
def calc_travel_time(dist):
    if dist <= 0: return 0
    return (dist * sec_per_floor) + accel_delay

if run_btn:
    # 1. 배치 결정 (자동 최적화 시 지하 비중 반영)
    best_floors = []
    if placement_method == "자동 최적화 추천":
        if current_mode == "morning":
            step = (total_fs - idx_1f) // (num_elevators + 1)
            best_floors = [int(idx_1f + (step * (i+1))) for i in range(num_elevators)]
        elif current_mode == "evening":
            # 주차장 비율이 높으면 일부는 지하 대기
            num_to_b = int(num_elevators * (p_ratio / 100))
            best_floors = [random.randint(0, idx_1f-1) for _ in range(num_to_b)] + [idx_1f] * (num_elevators - num_to_b)
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

    # 3. 성능 계산 (4개 핵심 노선)
    avg_high_f = idx_1f + (max_f * 0.6) 
    
    def analyze_node(start_idx, end_idx, target):
        min_dist = min([abs(f_idx - start_idx) for f_idx in best_floors])
        wait_time = calc_travel_time(min_dist)
        move_time = calc_travel_time(abs(start_idx - end_idx))
        total = wait_time + move_time + (door_time * 2) + (boarding_delay * 4)
        return total, total - target

    nodes = {
        "1F → 거주층": analyze_node(idx_1f, avg_high_f, target_1f_up),
        "거주층 → 1F": analyze_node(avg_high_f, idx_1f, target_1f_down),
        "지하 → 거주층": analyze_node(0, avg_high_f, target_b_up),
        "거주층 → 지하": analyze_node(avg_high_f, 0, target_b_down)
    }

    # 4. 결과 리포트
    st.divider()
    st.subheader("🔍 노선별 목표 대비 성능 분석")
    
    # 지상층 노선
    st.write("#### 🏢 지상 1층 로비 동선")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("1F ⬆️ 상행", f"{nodes['1F → 거주층'][0]:.1f}초", f"{nodes['1F → 거주층'][1]:+.1f}초", delta_color="inverse")
    with c2:
        st.metric("1F ⬇️ 하행", f"{nodes['거주층 → 1F'][0]:.1f}초", f"{nodes['거주층 → 1F'][1]:+.1f}초", delta_color="inverse")

    # 지하층 노선 (요청하신 분석 추가)
    st.write("#### 🚗 지하 주차장 동선")
    c3, c4 = st.columns(2)
    with c3:
        st.metric("지하 ⬆️ 상행", f"{nodes['지하 → 거주층'][0]:.1f}초", f"{nodes['지하 → 거주층'][1]:+.1f}초", delta_color="inverse")
    with c4:
        st.metric("지하 ⬇️ 하행", f"{nodes['거주층 → 지하'][0]:.1f}초", f"{nodes['거주층 → 지하'][1]:+.1f}초", delta_color="inverse")

    # 종합 리포트 테이블
    st.write("#### 📋 상세 분석 데이터")
    report_data = []
    for name, (time, diff) in nodes.items():
        status = f"✅ {abs(diff):.1f}초 단축" if diff <= 0 else f"⚠️ {diff:.1f}초 초과"
        report_data.append({"노선": name, "예상 시간": f"{time:.1f}초", "상태": status})
    
    st.table(pd.DataFrame(report_data))
