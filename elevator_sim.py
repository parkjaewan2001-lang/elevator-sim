import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("전략적 배치(AI/수동)와 무전략(1F 고정) 상태의 소요 시간 차이를 그래프로 분석합니다.")

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

run_btn = st.button("🚀 전략 비교 데이터 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: ENGINE -----------------

def calculate_time(start_idx, end_idx, placements):
    min_dist = min([abs(f_idx - start_idx) for f_idx in placements])
    wait_t = (min_dist * sec_per_floor) + accel_delay
    move_t = (abs(start_idx - end_idx) * sec_per_floor) + accel_delay
    household_weight = 1 + (households_per_floor * 0.03)
    total = (wait_t + move_t + (door_time * 2) + (1.2 * 4)) * household_weight
    if delivery_mode: total *= 1.3
    return total

if run_btn:
    basic_placements = [idx_1f] * num_elevators # 비최적화 (1F 고정)
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    nodes = {
        "1F ⬆️ 거주층": (idx_1f, avg_res_f, t_1f_up),
        "거주층 ⬇️ 1F": (avg_res_f, idx_1f, t_1f_down),
        "지하 ⬆️ 거주층": (0, avg_res_f, t_b_up),
        "거주층 ⬇️ 지하": (avg_res_f, 0, t_b_down)
    }

    st.subheader("📊 전략 적용 vs 미적용 성능 비교")
    
    report_list = []
    chart_data = []

    for name, (start, end, target) in nodes.items():
        # 전략 적용 시간 (AI 또는 수동 배치)
        strategy_time = calculate_time(start, end, final_placements)
        # 전략 미적용 시간 (전원 1F 대기)
        no_strategy_time = calculate_time(start, end, basic_placements)
        
        diff = strategy_time - no_strategy_time
        improvement = ((no_strategy_time - strategy_time) / no_strategy_time) * 100
        
        report_list.append({
            "노선": name,
            "전략 적용": f"{strategy_time:.1f}초",
            "전략 미적용": f"{no_strategy_time:.1f}초",
            "차이": f"{diff:+.1f}초",
            "개선율": f"{improvement:.1f}%"
        })
        
        chart_data.append({
            "노선": name,
            "현재 전략": strategy_time,
            "무전략(1F대기)": no_strategy_time
        })

    # 1. 상단 메트릭 리포트
    m_cols = st.columns(4)
    for i, item in enumerate(report_list):
        m_cols[i].metric(item["노선"], item["전략 적용"], item["차이"], delta_color="inverse")

    st.divider()

    # 2. 비교 그래프 (핵심 추가 기능)
    st.write("#### 📈 노선별 시간차이 비교 그래프")
    df_chart = pd.DataFrame(chart_data).set_index("노선")
    st.bar_chart(df_chart)
    st.caption("파란색 막대(현재 전략)가 빨간색/주황색 막대(무전략)보다 낮을수록 배치 로직의 효율이 높은 것입니다.")

    # 3. 상세 데이터 테이블
    st.write("#### 📋 상세 비교 데이터 시트")
    st.table(pd.DataFrame(report_list))

    with st.expander("📝 분석 결과 해석 가이드"):
        st.write("- **현재 전략:** 사용자가 수동으로 배치했거나 AI가 제안한 위치를 기반으로 한 예상 시간입니다.")
        st.write("- **무전략(1F대기):** 모든 엘리베이터가 로직 없이 1층에만 머물러 있을 때의 시간입니다.")
        st.write("- **그래프 편차:** 두 막대의 높이 차이가 클수록 현재 설정하신 배치 로직의 성능 개선 효과가 강력함을 의미합니다.")
