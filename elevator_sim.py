import streamlit as st
import pandas as pd
import numpy as np
import random

# ----------------- [1] UI 레이아웃 및 설정 -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")
st.caption("모든 기능 통합 및 제약 조건이 해제된 최종 시뮬레이션 환경입니다.")

# ----------------- [2] SIDEBAR: 건물/물리/세대/임계치 설정 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수 (밀도 가중치)", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (시뮬레이션 제외)", 1, 5, 3)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=2, max_value=10)

    st.divider()
    st.header("🚀 물리 엔진 설정")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)

    st.divider()
    st.header("⚡ 문 개폐 및 행동")
    base_door_time = st.number_input("기본 문 시간 (초)", value=7.0)
    button_efficiency = st.slider("🔘 닫힘 버튼 효율 (%)", 0, 100, 40)

    st.divider()
    st.header("⚠️ 서비스 임계치 세분화 (SLA)")
    lim_1f_up = st.slider("1층 → 거주층 (상행)", 30, 180, 60)
    lim_res_1f = st.slider("거주층 → 1층 (하행)", 30, 180, 80)
    lim_p_up = st.slider("주차장 → 거주층 (상행)", 30, 180, 70)
    lim_res_p = st.slider("거주층 → 주차장 (하행)", 30, 180, 90)

# ----------------- [3] MAIN PANEL: 전략 및 시나리오 -----------------
st.header("⚙️ 시뮬레이션 전략 자유 설정")

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

col_strat1, col_strat2 = st.columns(2)

# 운영 알고리즘 섹션 (독립 제어)
with col_strat1:
    st.subheader("🕹️ 운영 알고리즘")
    logic_option = st.selectbox(
        "운행 규칙 선택",
        ["사용 안 함 (전 층 자유 운행)", "홀짝수층 분리 운행", "저층/고층부 분할 운행"]
    )
    logic_type = "전 층 자유 운행 (기본)" if logic_option == "사용 안 함 (전 층 자유 운행)" else logic_option

# 배치 전략 섹션 (1층 고정 해제 및 독립 제어)
with col_strat2:
    st.subheader("📍 대기 위치 배치")
    placement_option = st.selectbox(
        "배치 방식 선택",
        ["사용 안 함 (전 층 균등 분포)", "AI 자동 최적화 배치", "사용자 수동 배치"]
    )

st.divider()

# 배치 로직 처리 (모든 케이스 반영)
final_placements = []
mode_label = ""

if placement_option == "사용 안 함 (전 층 균등 분포)":
    mode_label = "균등 분포"
    final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    st.info("💡 배치 전략 미사용: 엘리베이터가 건물 전 층에 골고루 분산된 상태로 시작합니다.")

elif placement_option == "AI 자동 최적화 배치":
    mode_label = st.select_slider("⏰ 시간대 패턴 설정", options=["새벽 시간", "출근 시간", "낮 시간", "퇴근 시간"], value="낮 시간")
    if mode_label == "새벽 시간":
        final_placements = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2)
    elif mode_label == "출근 시간":
        final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    elif mode_label == "퇴근 시간":
        final_placements = [idx_1f] * num_elevators
    else: # 낮 시간
        final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
        
elif placement_option == "사용자 수동 배치":
    mode_label = "수동 지정"
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)} 대기층", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            final_placements.append(val)

# 현재 배치 상태 시각화
st.write(f"**현재 설정된 배치 상태 ({mode_label}):**")
disp_cols = st.columns(num_elevators)
for i, p in enumerate(final_placements):
    disp_cols[i].metric(f"EL {chr(65+i)}", FLOOR_LABELS[p])

st.divider()

# 환경 가중치 설정
st.subheader("🌐 환경 변수 및 가중치")
c_env1, c_env2, c_env3 = st.columns(3)
with c_env1: congestion = st.select_slider("건물 혼잡도", options=["매우 쾌적", "보통", "매우 혼잡"], value="보통")
with c_env2: delivery = st.toggle("📦 배송/택배 지연 모드", value=(mode_label == "새벽 시간"))
with c_env3: dynamic_door = st.toggle("🚪 동적 문 개폐 로직 적용", value=True)

# ----------------- [4] LOGIC: 시뮬레이션 엔진 -----------------

def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel:
        return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route(start, end, placements, logic, cong, is_deliv, eff, door_active):
    # 혼잡 가중치
    w_map = {"매우 쾌적": 0.7, "보통": 1.1, "매우 혼잡": 2.5}
    w = w_map[cong]
    
    # 1. 알고리즘에 따른 응답 가능 필터링
    actual_f = start - min_f
    avail = []
    for i in range(num_elevators):
        if logic == "전 층 자유 운행 (기본)": avail.append(i)
        elif logic == "홀짝수층 분리 운행":
            if start == idx_1f or (i%2 == 0 and actual_f%2 != 0) or (i%2 != 0 and actual_f%2 == 0): avail.append(i)
        elif logic == "저층/고층부 분할 운행":
            mid = total_fs // 2
            if start == idx_1f or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid): avail.append(i)
    
    if not avail: avail = list(range(num_elevators))
    
    # 2. 대기 시간 (물리 엔진)
    min_dist_m = min([abs(placements[i] - start) for i in avail]) * floor_height
    wait_t = get_phys_time(min_dist_m, max_velocity, acceleration)
    
    # 3. 이동 시간 (물리 엔진)
    move_t = get_phys_time(abs(start - end) * floor_height, max_velocity, acceleration)
    
    # 4. 문 개폐 (동적 로직)
    is_inside = True if start > idx_1f else False
    if door_active and is_inside:
        door_t = base_door_time * (1 - (eff/100))
    else:
        door_t = base_door_time * 1.2
    
    # 5. 최종 가중치 합산 (세대 밀도 반영)
    loading_t = (door_t * w) * (1 + (households_per_floor * 0.05))
    total_t = wait_t + move_t + loading_t
    
    # 배송 가중치
    if is_deliv: total_t *= 1.4 if mode_label == "새벽 시간" else 1.3
    
    return total_t

# ----------------- [5] EXECUTION & REPORT -----------------
if st.button("🚀 통합 정밀 시뮬레이션 실행", type="primary", use_container_width=True):
    avg_res_f = idx_1f + stairs_floor + ((max_f - stairs_floor) * 0.7)
    
    # 4대 노선 시나리오 (사용자 요청 세분화)
    scenarios = {
        "1층 ⬆️ 거주층": (idx_1f, avg_res_f, lim_1f_up),
        "거주층 ⬇️ 1층": (avg_res_f, idx_1f, lim_res_1f),
        "주차장 ⬆️ 거주층": (0, avg_res_f, lim_p_up),
        "거주층 ⬇️ 주차장": (avg_res_f, 0, lim_res_p)
    }

    st.subheader(f"📊 분석 결과 리포트 (모드: {mode_label})")
    st.write(f"현재 전략: `{logic_option}` + `{placement_option}`")

    res_cols = st.columns(4)
    chart_data = []
    
    for i, (name, (s, e, l)) in enumerate(scenarios.items()):
        total_time = simulate_route(s, e, final_placements, logic_type, congestion, delivery, button_efficiency, dynamic_door)
        is_exceed = total_time > l
        
        with res_cols[i]:
            st.metric(name, f"{total_time:.1f}초", f"목표 {l}s", delta_color="normal" if not is_exceed else "inverse")
            if is_exceed: st.error("🚨 지연 발생")
            else: st.success("✅ 통과")
        
        chart_data.append({"노선": name, "소요 시간": total_time, "임계치": l})

    st.divider()
    st.bar_chart(pd.DataFrame(chart_data).set_index("노선"))
    st.info("📍 분석 결과는 설정된 물리 엔진과 동적 문 개폐 로직, 그리고 선택된 시간대 패턴의 누적 가중치를 기반으로 산출되었습니다.")
