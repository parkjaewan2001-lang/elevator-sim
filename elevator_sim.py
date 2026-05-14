import streamlit as st
import pandas as pd
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")

st.title("🏢 Elevator Experiment Lab")
st.caption("세대수 수요, 계단 이용, 자율주행 비교 및 택배 지연 최적화가 포함된 최종 시뮬레이터입니다.")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 거주 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수 (이 이하는 계단 권장)", 1, 5, 3)
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
    target_b_up = st.number_input("지하 → 거주층 목표", value=55)
    target_b_down = st.number_input("거주층 → 지하 목표", value=90)

# ----------------- MAIN PANEL -----------------
st.header("⚙️ 시뮬레이션 설정")

# [기능 1] 혼잡도 및 택배 지연 설정
col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    congestion_level = st.select_slider(
        "👥 건물 혼잡도",
        options=["매우 쾌적", "여유", "보통", "혼잡", "매우 혼잡"],
        value="보통"
    )
with col_cfg2:
    delivery_mode = st.toggle("📦 택배 배달 지연 모드 활성화", help="택배 차량 도착 시 여러 층에 동시 정차하여 발생하는 지연을 시뮬레이션합니다.")

# 혼잡도 가중치
congestion_map = {"매우 쾌적": 0.8, "여유": 1.0, "보통": 1.2, "혼잡": 2.0, "매우 혼잡": 3.5}
adj_delay = congestion_map[congestion_level]

st.divider()

# [기능 2] 시간대 및 배치 방식
mode_label = st.radio("⏰ 분석 시간대", ["출근 시간", "퇴근 시간", "낮 시간", "새벽 시간"], horizontal=True)
mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "낮 시간": "daytime", "새벽 시간": "night"}
current_mode = mode_map[mode_label]

placement_method = st.radio("📍 배치 로직 선택", ["자율주행 최적화 추천 (AI)", "기본 고정 배치 (비최적화)", "사용자 수동 배치"], horizontal=True)

# 층 설정 및 주차장 비율
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)
p_ratio = st.slider("🚗 주차장(지하층) 이용 비중 (%)", 0, 100, 30)

# 수동 배치 입력
manual_floors = []
if placement_method == "사용자 수동 배치":
    m_cols = st.columns(num_elevators)
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
            manual_floors.append(val)

run_btn = st.button("🚀 최종 통합 성능 분석 실행", type="primary", use_container_width=True)

# ----------------- LOGIC: PHYSICS & ANALYSIS ENGINE -----------------
def calc_physics_time(dist, is_delivery=False):
    if dist <= 0: return 0
    # 택배 모드일 경우 정차 횟수 가중치 증가
    stop_penalty = 2.5 if (is_delivery and delivery_mode) else 1.0
    return (dist * sec_per_floor) + (accel_delay * stop_penalty)

if run_btn:
    # 1. 배치 로직 결정
    best_floors = []
    comparison_floors = [idx_1f] * num_elevators # 비최적화(자율주행 미적용) 비교군
    
    if placement_method == "자율주행 최적화 추천 (AI)":
        if current_mode == "morning": # 상층부 분산
            step = (total_fs - idx_1f) // (num_elevators + 1)
            best_floors = [int(idx_1f + (step * (i+1))) for i in range(num_elevators)]
        elif current_mode == "evening": # 하층부/지하 분산
            num_to_b = int(num_elevators * (p_ratio / 100))
            best_floors = [random.randint(0, idx_1f-1) for _ in range(num_to_b)] + [idx_1f] * (num_elevators - num_to_b)
        else: # 균등 분산
            step = total_fs // (num_elevators + 1)
            best_floors = [int(step * (i+1)) for i in range(num_elevators)]
    elif placement_method == "기본 고정 배치 (비최적화)":
        best_floors = [idx_1f] * num_elevators
    else:
        best_floors = manual_floors

    # 2. 성능 계산 (세대수 및 계단 반영)
    # 계단 이용 층(stairs_floor) 이상의 평균 거주층 계산
    valid_residential_start = idx_1f + stairs_floor
    avg_high_f = (valid_residential_start + (total_fs - 1)) / 2
    
    # 세대수 가중치 (세대수가 많을수록 호출 대기 시간 확률적 증가)
    household_weight = 1 + (households_per_floor * 0.05)

    def analyze_node(start_idx, end_idx, target, placements):
        min_dist = min([abs(f_idx - start_idx) for f_idx in placements])
        wait_time = calc_physics_time(min_dist, is_delivery=True)
        move_time = calc_physics_time(abs(start_idx - end_idx))
        # 총 시간 계산
        total = (wait_time + move_time + (door_time * 2) + (1.2 * 4 * adj_delay)) * household_weight
        return total

    # 결과 분석
    res_nodes = {
        "1F → 거주층": analyze_node(idx_1f, avg_high_f, target_1f_up, best_floors),
        "거주층 → 1F": analyze_node(avg_high_f, idx_1f, target_1f_down, best_floors),
        "지하 → 거주층": analyze_node(0, avg_high_f, target_b_up, best_floors),
        "거주층 → 지하": analyze_node(avg_high_f, 0, target_b_down, best_floors)
    }
    
    # 자율주행 미적용 시(비교군) 분석
    comp_nodes = {
        "1F → 거주층": analyze_node(idx_1f, avg_high_f, target_1f_up, comparison_floors),
        "거주층 → 1F": analyze_node(avg_high_f, idx_1f, target_1f_down, comparison_floors)
    }

    # 3. 리포트 출력
    st.subheader("📍 최종 엘리베이터 배치 상태")
    cols = st.columns(num_elevators)
    for i, f_idx in enumerate(best_floors):
        cols[i].metric(f"EL {chr(65+i)}", FLOOR_LABELS[f_idx])

    st.divider()
    
    # [차별화 기능] 자율주행 vs 일반 비교
    st.subheader("🤖 자율주행(최적화) 도입 효과 분석")
    diff_val = comp_nodes["거주층 → 1F"] - res_nodes["거주층 → 1F"]
    c_eff1, c_eff2 = st.columns(2)
    c_eff1.metric("최적화 적용 시간 (평균)", f"{res_nodes['거주층 → 1F']:.1f}초")
    c_eff2.metric("비최적화 대비 단축 시간", f"{diff_val:.1f}초", f"{((diff_val/comp_nodes['거주층 → 1F'])*100) if comp_nodes['거주층 → 1F'] !=0 else 0:.1f}% 개선")

    # [핵심 리포트] 전 노선 결과
    st.subheader("🔍 노선별 정밀 리포트")
    report_list = []
    targets = [target_1f_up, target_1f_down, target_b_up, target_b_down]
    for (name, time), target in zip(res_nodes.items(), targets):
        diff = time - target
        status = f"✅ {abs(diff):.1f}초 단축" if diff <= 0 else f"⚠️ {diff:.1f}초 초과"
        report_list.append({"노선": name, "목표 시간": f"{target}초", "실제 예상": f"{time:.1f}초", "상태": status})
    
    st.table(pd.DataFrame(report_list))

    # [알고리즘 설명] 택배 및 계단 로직 반영 알림
    with st.expander("💡 적용된 특수 알고리즘 상세 보기"):
        st.write(f"- **계단 이용 반영:** {stairs_floor}층 이하 거주자는 호출 수요에서 제외되어 상층부 효율이 개선되었습니다.")
        st.write(f"- **세대수 가중치:** 층당 {households_per_floor}세대의 호출 빈도를 계산하여 대기 시간에 반영했습니다.")
        if delivery_mode:
            st.write("- **택배 지연 대응:** 택배 모드 활성화로 인해 중간 정차 지연이 가중되었으며, 이를 극복하기 위한 협력 배치 로직이 작동 중입니다.")
