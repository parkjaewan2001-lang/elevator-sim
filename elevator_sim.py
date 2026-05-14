import streamlit as st
import pandas as pd
import numpy as np

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("시간대별 패턴, 지하 주차장 비중, 그리고 AI 최적화의 효과를 정밀 분석합니다.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 거주 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (분석 제외)", 1, 5, 3)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10)

    st.divider()

    st.header("⚡ 물리 및 가속도 설정")
    sec_per_floor = st.number_input("정속 주행 시 층당 시간(초)", value=1.0)
    accel_delay = st.number_input("가속/감속 추가 지연(초)", value=1.5)
    door_time = st.number_input("문 개폐 시간(초)", value=7.0)

    st.divider()
    
    st.header("🎯 목표 시간(초)")
    t_1f_up = st.number_input("1F → 거주층 목표", value=45)
    t_1f_down = st.number_input("거주층 → 1F 목표", value=80)
    t_b_up = st.number_input("지하 → 거주층 목표", value=55)
    t_b_down = st.number_input("거주층 → 지하 목표", value=90)

# ----------------- MAIN PANEL: SCENARIO SETTINGS -----------------
st.header("⚙️ 시뮬레이션 시나리오")

# 1. 시간대 설정 (부활)
mode_label = st.radio(
    "⏰ 분석 시간대 선택", 
    ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], 
    horizontal=True
)
mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "낮 시간": "daytime", "새벽 시간": "night"}
current_mode = mode_map[mode_label]

# 2. 주차장 이용 비율 설정 (부활)
st.subheader("🚗 주차장(지하) 이용 비중 설정")
c_p1, c_p2 = st.columns(2)
with c_p1:
    p_up_ratio = st.slider("지하에서 올라가는 비율 (%)", 0, 100, 30, help="지하 주차장에서 탑승하여 거주층으로 가는 승객 비율")
with c_p2:
    p_down_ratio = st.slider("지하로 내려가는 비율 (%)", 0, 100, 40, help="거주층에서 탑승하여 지하 주차장으로 가는 승객 비율")

# 3. 기타 변수
col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    congestion_level = st.select_slider("👥 건물 혼잡도", options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡"], value="보통")
with col_cfg2:
    delivery_mode = st.toggle("📦 택배 배달 지연 모드 활성화")

# 가중치 계산
congestion_map = {"매우 쾌적": 0.8, "여유": 1.0, "보통": 1.2, "혼잡": 2.0, "매우 혼잡": 3.5}
adj_delay = congestion_map[congestion_level]
household_weight = 1 + (households_per_floor * 0.03)

st.divider()

# 4. 배치 로직 선택
placement_method = st.radio("📍 로직 선택", ["자율주행 최적화 (AI 추천)", "기본 고정 배치 (전원 1F 대기)"], horizontal=True)

# 층 정보 정의
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

run_btn = st.button("🚀 통합 성능 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: ENGINE -----------------

def get_wait_dist(start_idx, placements, is_optimized):
    """대수 증가에 따른 대기 시간 감소 로직"""
    if is_optimized:
        return min([abs(f_idx - start_idx) for f_idx in placements])
    else:
        # 비최적화(1층 고정) 시에도 대수가 많으면 확률적으로 15%씩 응답 효율 상승
        base_dist = abs(placements[0] - start_idx)
        efficiency = max(0.4, (1 - (0.15 * (len(placements) - 1))))
        return base_dist * efficiency

def calculate_time(start_idx, end_idx, placements, is_optimized):
    # 가속도를 고려한 대기 및 이동 시간
    d_call = get_wait_dist(start_idx, placements, is_optimized)
    wait_t = (d_call * sec_per_floor) + accel_delay
    
    d_move = abs(start_idx - end_idx)
    move_t = (d_move * sec_per_floor) + accel_delay
    
    # 최종 시간 (혼잡도, 세대수, 택배 반영)
    total = (wait_t + move_t + (door_time * 2) + (1.2 * 4 * adj_delay)) * household_weight
    if delivery_mode: total *= 1.3
    return total

if run_btn:
    # 1. AI 최적화 배치 시나리오
    if current_mode == "morning": # 출근: 거주층 분산 배치
        opt_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    elif current_mode == "evening": # 퇴근: 1F 및 지하 주차장 비중에 따라 분산
        num_b = int(num_elevators * (max(p_up_ratio, p_down_ratio) / 100))
        opt_placements = [random.randint(0, idx_1f-1) for _ in range(num_b)] + [idx_1f] * (num_elevators - num_b)
    else: # 평시: 전체 균등 분산
        opt_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    
    # 2. 기본 고정 배치 (대조군)
    basic_placements = [idx_1f] * num_elevators
    
    # 현재 선택된 모드 적용
    is_ai = "AI" in placement_method
    current_placements = opt_placements if is_ai else basic_placements
    compare_placements = basic_placements if is_ai else opt_placements

    # 3. 성능 분석 (4대 주요 노선)
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    
    nodes = {
        "1F ⬆️ 거주층": (idx_1f, avg_res_f, t_1f_up),
        "거주층 ⬇️ 1F": (avg_res_f, idx_1f, t_1f_down),
        "지하 ⬆️ 거주층": (0, avg_res_f, t_b_up),
        "거주층 ⬇️ 지하": (avg_res_f, 0, t_b_down)
    }

    # 리포트 생성
    st.subheader(f"📊 분석 결과 (시간대: {mode_label} / 방식: {placement_method})")
    
    # 메트릭 표시
    m_cols = st.columns(4)
    report_data = []
    
    for i, (name, (start, end, target)) in enumerate(nodes.items()):
        cur_time = calculate_time(start, end, current_placements, is_ai)
        alt_time = calculate_time(start, end, compare_placements, not is_ai)
        diff = cur_time - alt_time
        
        with m_cols[i]:
            st.metric(name, f"{cur_time:.1f}초", f"{diff:+.1f}초", delta_color="inverse")
        
        status = f"✅ {abs(cur_time - target):.1f}초 단축" if cur_time <= target else f"⚠️ {cur_time - target:.1f}초 초과"
        report_data.append({"노선": name, "목표": f"{target}초", "예상": f"{cur_time:.1f}초", "상태": status})

    # 상세 정보
    st.divider()
    c_left, c_right = st.columns([1, 2])
    
    with c_left:
        st.write("#### 📍 엘리베이터 대기 위치")
        for j, p in enumerate(current_placements):
            st.write(f"**EL {chr(65+j)}**: {FLOOR_LABELS[p]}")
        
        st.info(f"💡 **분석 요약:** {'AI 최적화' if is_ai else '기본 배치'}가 적용되어 있으며, {'비최적화' if is_ai else 'AI 최적화'} 대비 변화량이 표시됩니다.")

    with c_right:
        st.write("#### 📋 상세 분석 데이터")
        st.table(pd.DataFrame(report_data))

    # 차트 (대수별 효율)
    st.write("#### 📈 엘리베이터 대수 증가에 따른 하행(거주층→1F) 성능 변화")
    chart_list = []
    for n in range(1, 11):
        test_bas = [idx_1f] * n
        test_opt = [int(f) for f in np.linspace(0, total_fs-1, n)]
        chart_list.append({
            "대수": n, 
            "기본 고정 배치": calculate_time(avg_res_f, idx_1f, test_bas, False),
            "AI 자율주행": calculate_time(avg_res_f, idx_1f, test_opt, True)
        })
    st.line_chart(pd.DataFrame(chart_list).set_index("대수"))
