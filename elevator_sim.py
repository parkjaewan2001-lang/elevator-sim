import streamlit as st
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Apartment Life Simulator", layout="wide")

st.title("🏢 Apartment Life Simulator Pro")
st.caption("가구 밀도 및 배달/방문객 등 일상적인 이동 로직이 포함된 시뮬레이션")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 상세 설정")
    max_f = st.number_input("최고 층 (지상)", min_value=1, max_value=100, value=30)
    min_f = st.number_input("최저 층 (지하)", min_value=0, max_value=20, value=5)
    # 신규 추가: 한 층당 거주 세대수
    households_per_floor = st.slider("한 층당 거주 세대수", 1, 10, 4)
    num_elevators = st.slider("엘리베이터 개수", 1, 10, 2)
    
    st.divider()
    
    st.header("⚡ 물리 및 지연 설정")
    sec_per_floor = st.number_input("한 층 이동 시간 (초)", value=2.5)
    door_time = st.number_input("문 개폐 시간 (초)", value=7.0)
    boarding_delay = st.slider("인당 탑승/하차 지연 (초)", 0.5, 5.0, 1.2)

    st.divider()
    
    st.header("⚙️ 시나리오 설정")
    mode_label = st.radio("시간대 선택", ["출근 시간", "퇴근 시간", "평상시 (낮/밤)"])
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "평상시 (낮/밤)": "normal"}
    current_mode = mode_map[mode_label]
    
    # 평상시일 경우 배달/택배 비중 조절
    delivery_ratio = 0
    if current_mode == "normal":
        delivery_ratio = st.slider("배달/방문객 발생 빈도 (%)", 0, 100, 30, help="높을수록 층간 무작위 이동이 많아집니다.")

    run_btn = st.button("시뮬레이션 실행", type="primary", use_container_width=True)

# ----------------- LOGIC HELPER -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
TOTAL_FLOORS = len(FLOOR_LABELS)
idx_1f = min_f
total_households = max_f * households_per_floor # 전체 세대 수

# ----------------- SIMULATION ENGINE -----------------
def run_simulation(mode, f1_idx, total_fs, s_per_f, d_time, b_delay, d_ratio, h_per_f):
    stats = {'resTo1F': [], 'f1ToRes': [], 'delivery': []}
    elevator_positions = [f1_idx] * num_elevators
    
    # 가구 밀도에 따른 호출 가중치 (가구가 많을수록 시뮬레이션 횟수 보정)
    iterations = 1000 + (h_per_f * 100)

    for _ in range(iterations):
        r = random.random()
        
        # 1. 이동 경로 생성 (로직 다변화)
        if mode == 'morning': # 출근 집중
            start_idx = random.randint(f1_idx + 1, total_fs - 1)
            end_idx = random.randint(0, f1_idx)
        elif mode == 'evening': # 퇴근 집중
            start_idx = random.randint(0, f1_idx)
            end_idx = random.randint(f1_idx + 1, total_fs - 1)
        else: # 평상시 (배달 및 일반 이동)
            if r < (d_ratio / 100.0):
                # 배달 로직: 1층에서 특정 층으로 갔다가, 다시 1층으로 복귀하는 특성 반영
                start_idx = f1_idx
                end_idx = random.randint(f1_idx + 1, total_fs - 1)
                is_delivery = True
            else:
                # 일반 이동: 거주민간 이동 또는 외출
                start_idx = random.randint(0, total_fs - 1)
                end_idx = random.randint(0, total_fs - 1)
                is_delivery = False

        if start_idx == end_idx: continue

        # 2. 가장 가까운 엘리베이터 배정
        dists = [abs(pos - start_idx) for pos in elevator_positions]
        chosen = dists.index(min(dists))
        
        # 3. 시간 계산 (지연 시간 포함)
        # 가구 수가 많을수록 탑승 인원이 겹칠 확률이 높으므로 지연 시간 보정
        pax_count = random.randint(1, min(h_per_f, 5))
        total_delay = pax_count * b_delay
        
        total_time = (min(dists) * s_per_f) + (abs(start_idx - end_idx) * s_per_f) + (d_time * 2) + (total_delay * 2)
        
        elevator_positions[chosen] = end_idx
        
        # 4. 결과 기록
        if mode != 'normal':
            if start_idx > f1_idx and end_idx <= f1_idx: stats['resTo1F'].append(total_time)
            else: stats['f1ToRes'].append(total_time)
        else:
            if is_delivery: stats['delivery'].append(total_time)
            else: stats['resTo1F'].append(total_time)

    return stats

# ----------------- OUTPUT -----------------
if run_btn:
    results = run_simulation(current_mode, idx_1f, TOTAL_FLOORS, sec_per_floor, door_time, boarding_delay, delivery_ratio, households_per_floor)
    
    st.subheader(f"📊 {mode_label} 분석 리포트")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.metric("전체 가구 수", f"{total_households} 세대")
        st.caption(f"층당 {households_per_floor}세대 거주 중")
        
    if current_mode == "normal":
        with c2:
            avg_del = sum(results['delivery'])/len(results['delivery']) if results['delivery'] else 0
            st.metric("배달/방문 평균 시간", f"{avg_del:.1f}초")
        with c3:
            st.info("평상시에는 배달원과 방문객의 유입으로 인해 1층 호출 빈도가 불규칙하게 발생합니다.")
    else:
        avg_res = sum(results['resTo1F'])/len(results['resTo1F']) if results['resTo1F'] else 0
        with c2:
            st.metric("평균 이동 시간", f"{avg_res:.1f}초")
        with c3:
            st.write("출퇴근 시간에는 특정 방향으로 인원이 쏠려 대기 시간이 길어질 수 있습니다.")
