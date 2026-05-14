import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("노선별 최대 대기 시간 임계치를 설정하여 배치 로직의 안정성을 진단합니다.")

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
    
    # [부활] 노선별 최대 대기 시간 설정
    st.header("⚠️ 최대 허용 대기 시간 설정 (초)")
    limit_1f_up = st.slider("1F → 거주층 최대치", 30, 120, 45)
    limit_1f_down = st.slider("거주층 → 1F 최대치", 30, 180, 80)
    limit_b_up = st.slider("지하 → 거주층 최대치", 30, 150, 60)
    limit_b_down = st.slider("거주층 → 지하 최대치", 30, 180, 90)

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

placement_mode = st.radio("📍 배치 방식 선택", ["AI 자동 최적화 분석", "사용자 수동 배치"], horizontal=True)

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

final_placements = []
if placement_mode == "사용자 수동 배치":
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
    
    cols = st.columns(num_elevators)
    for i, p in enumerate(final_placements):
        cols[i].metric(f"EL {chr(65+i)} 배치", FLOOR_LABELS[p])

run_btn = st.button("🚀 성능 및 한계치 분석 실행", type="primary", use_container_width=True)

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
    # 무작위 분산 대조군 계산용 함수
    def get_random_avg(start, end, n):
        return sum([calculate_time(start, end, [random.randint(0, total_fs-1) for _ in range(n)]) for _ in range(10)]) / 10

    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.6)
    nodes = {
        "1F ⬆️ 거주층": (idx_1f, avg_res_f, limit_1f_up),
        "거주층 ⬇️ 1F": (avg_res_f, idx_1f, limit_1f_down),
        "지하 ⬆️ 거주층": (0, avg_res_f, limit_b_up),
        "거주층 ⬇️ 지하": (avg_res_f, 0, limit_b_down)
    }

    st.subheader("📊 성능 및 임계치 통과 여부")
    m_cols = st.columns(4)
    report_list = []
    chart_data = []

    for i, (name, (start, end, limit)) in enumerate(nodes.items()):
        strategy_time = calculate_time(start, end, final_placements)
        random_time = get_random_avg(start, end, num_elevators)
        
        # 임계치 초과 여부 확인
        is_exceeded = strategy_time > limit
        status_color = "normal" if not is_exceeded else "inverse"
        status_msg = "✅ 통과" if not is_exceeded else f"🚨 초과 (+{strategy_time - limit:.1f}초)"

        with m_cols[i]:
            st.metric(name, f"{strategy_time:.1f}초", f"한계: {limit}초", delta_color=status_color)
            st.caption(status_msg)
        
        report_list.append({
            "노선": name,
            "현재 전략": f"{strategy_time:.1f}초",
            "최대 허용치": f"{limit}초",
            "결과": status_msg,
            "무작위 분산 대비": f"{strategy_time - random_time:+.1f}초"
        })
        chart_data.append({"노선": name, "현재 전략": strategy_time, "최대 허용치": limit, "무작위 분산": random_time})

    st.divider()

    # 시각화 그래프
    st.write("#### 📈 전략 성능 vs 최대 허용 임계치 비교")
    df_chart = pd.DataFrame(chart_data).set_index("노선")
    st.bar_chart(df_chart)
    st.info("💡 **팁:** '현재 전략' 막대가 '최대 허용치' 선보다 낮게 유지되도록 배치를 조정하는 것이 목표입니다.")

    st.write("#### 📋 상세 분석 데이터")
    st.table(pd.DataFrame(report_list))
