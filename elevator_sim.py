import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("전략적 배치 vs 무작위 분산(로직 없음) 상태의 현실적인 성능 차이를 분석합니다.")

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

# ----------------- MAIN PANEL: SCENARIO SETTINGS -----------------
st.header("⚙️ 시뮬레이션 시나리오 및 배치")

c_sc1, c_sc2 = st.columns(2)
with c_sc1:
    mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], horizontal=True)
with c_sc2:
    delivery_mode = st.toggle("📦 택배 배달 지연 모드 활성화")

st.subheader("🚗 주차장(지하) 이용 비중")
c_p1, c_p2 = st.columns(2)
with c_p1: p_up_ratio = st.slider("지하에서 올라가는 비율 (%)", 0, 100, 30)
with c_p2: p_down_ratio = st.slider("지하로 내려가는 비율 (%)", 0, 100, 40)

st.divider()

placement_mode = st.radio(
    "📍 배치 방식 선택", 
    ["AI 자동 최적화 분석 (코드 기반)", "사용자 수동 배치 시뮬레이션"], 
    horizontal=True
)

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

# 배치 결정 로직
final_placements = []
if placement_mode == "사용자 수동 배치 시뮬레이션":
    st.info("각 엘리베이터의 대기 위치를 직접 지정하세요.")
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            final_placements.append(val)
else:
    # AI 최적화 알고리즘
    if mode_label == "출근 시간":
        final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    elif mode_label == "퇴근 시간":
        num_b = int(num_elevators * (max(p_up_ratio, p_down_ratio) / 100))
        final_placements = [random.randint(0, idx_1f-1) for _ in range(num_b)] + [idx_1f] * (num_elevators - num_b)
    else:
        final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    
    st.success(f"🤖 AI 최적화 로직 적용됨")
    cols = st.columns(num_elevators)
    for i, p in enumerate(final_placements):
        cols[i].metric(f"EL {chr(65+i)} 배치", FLOOR_LABELS[p])

run_btn = st.button("🚀 무작위 분산 대조 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: ENGINE -----------------

def calculate_time(start_idx, end_idx, placements):
    # 가장 가까운 엘리베이터와의 거리 계산
    min_dist = min([abs(f_idx - start_idx) for f_idx in placements])
    wait_t = (min_dist * sec_per_floor) + accel_delay
    move_t = (abs(start_idx - end_idx) * sec_per_floor) + accel_delay
    
    household_weight = 1 + (households_per_floor * 0.03)
    total = (wait_t + move_t + (door_time * 2) + (1.2 * 4)) * household_weight
    if delivery_mode: total *= 1.3
    return total

if run_btn:
    # [핵심 변경] 비최적화 대조군: 1층 고정이 아닌 무작위 층 분산 (10회 시뮬레이션 평균값 사용)
    def get_random_average_time(start, end, n_el):
        trials = 10
        total_trial_time = 0
        for _ in range(trials):
            random_pos = [random.randint(0, total_fs - 1) for _ in range(n_el)]
            total_trial_time += calculate_time(start, end, random_pos)
        return total_trial_time / trials

    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    nodes = {
        "1F ⬆️ 거주층": (idx_1f, avg_res_f),
        "거주층 ⬇️ 1F": (avg_res_f, idx_1f),
        "지하 ⬆️ 거주층": (0, avg_res_f),
        "거주층 ⬇️ 지하": (avg_res_f, 0)
    }

    st.subheader("📊 전략 배치 vs 무작위 분산(무전략) 비교")
    
    report_list = []
    chart_data = []

    for name, (start, end) in nodes.items():
        # 1. 현재 전략 시간
        strategy_time = calculate_time(start, end, final_placements)
        # 2. 무작위 분산 평균 시간
        random_time = get_random_average_time(start, end, num_elevators)
        
        diff = strategy_time - random_time
        improvement = ((random_time - strategy_time) / random_time) * 100
        
        report_list.append({
            "노선": name,
            "전략 적용": f"{strategy_time:.1f}초",
            "무작위 분산(기본)": f"{random_time:.1f}초",
            "차이": f"{diff:+.1f}초",
            "효율 개선": f"{improvement:.1f}%"
        })
        
        chart_data.append({
            "노선": name,
            "현재 전략": strategy_time,
            "무작위 분산(무전략)": random_time
        })

    # 상단 메트릭
    m_cols = st.columns(4)
    for i, item in enumerate(report_list):
        m_cols[i].metric(item["노선"], item["전략 적용"], item["차이"], delta_color="inverse")

    st.divider()

    # 비교 그래프
    st.write("#### 📈 전략 배치 vs 무작위 분산 비교 그래프")
    df_chart = pd.DataFrame(chart_data).set_index("노선")
    st.bar_chart(df_chart)
    st.caption("무작위로 흩어져 있는 엘리베이터(무전략) 대비 현재 배치 전략의 우수성을 보여줍니다.")

    # 상세 데이터 테이블
    st.write("#### 📋 상세 분석 결과 데이터")
    st.table(pd.DataFrame(report_data := report_list))

    with st.expander("💡 분석 로직 안내"):
        st.write("- **무작위 분산(기본):** 엘리베이터가 모든 층에 불규칙하게 흩어져 있는 상태를 가정하여 10회 반복 측정 후 평균값을 산출했습니다.")
        st.write("- **전략 적용:** AI가 계산한 최적 위치 또는 사용자가 직접 지정한 위치에 대기할 때의 시간입니다.")
        st.write("- **현실성 강화:** 단순히 1층에 모여 있는 것보다 실제 운행 중인 엘리베이터의 불확실성을 더 잘 반영합니다.")
