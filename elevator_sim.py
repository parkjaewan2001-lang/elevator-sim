import streamlit as st
import random

# ----------------- STREAMLIT UI -----------------
st.set_page_config(page_title="Custom Arena Simulator", layout="wide")

st.title("🏢 Custom Arena Simulator")
st.caption("사용자가 직접 건물 규모를 설정하는 엘리베이터 시뮬레이션")

# Sidebar Controls
with st.sidebar:
    st.header("🏗️ 건물 규모 설정")
    # 사용자가 직접 층수를 정하는 부분
    max_f = st.number_input("최고 층 (지상)", min_value=1, max_value=100, value=30)
    min_f = st.number_input("최저 층 (지하)", min_value=0, max_value=20, value=5)
    
    # 설정된 층수에 따라 FLOOR_LABELS 자동 생성
    # 지하층(B) 생성 후 지상층(F) 생성
    FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
    TOTAL_FLOORS = len(FLOOR_LABELS)
    idx_1f = min_f  # 1층의 인덱스 위치 (지하 층수만큼 뒤에 있음)

    st.divider()
    
    st.header("⚙️ 시뮬레이션 설정")
    mode_label = st.radio("시간대 선택", ["출근 시간", "퇴근 시간", "그 외 시간"])
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "그 외 시간": "normal"}
    current_mode = mode_map[mode_label]
    
    st.subheader("대기 층 전략")
    # 동적으로 생성된 FLOOR_LABELS를 옵션으로 사용
    idle_a = st.select_slider("Elevator A 대기 층", options=FLOOR_LABELS, value=FLOOR_LABELS[len(FLOOR_LABELS)//2])
    idle_b = st.select_slider("Elevator B 대기 층", options=FLOOR_LABELS, value="1F")
    
    run_btn = st.button("시뮬레이션 실행", type="primary", use_container_width=True)

# ----------------- CONSTANTS & HELPERS -----------------
TARGETS = {'resTo1F': 83, 'f1ToRes': 47, 'resToB': 75}
TIME_PER_FLOOR = 2.5
DOOR_CYCLE = 7.0

# 층 성격 판단 함수 (동적 인덱스 기준)
def is_res(idx, f1_idx): return idx > f1_idx + 4 # 1층 위로 5개 층 이상부터 거주층으로 가정
def is_b(idx, f1_idx): return idx < f1_idx      # 1층보다 낮으면 지하
def is_1f(idx, f1_idx): return idx == f1_idx    # 1층

# ----------------- SIMULATION ENGINE -----------------
def run_simulation(mode, idle_a_idx, idle_b_idx, f1_idx, total_fs):
    stats = {'resTo1F': [], 'f1ToRes': [], 'resToB': []}
    num_trips = 1000
    pos_a, pos_b = idle_a_idx, idle_b_idx

    for _ in range(num_trips):
        start_idx, end_idx = 0, 0
        r = random.random()

        # 모드별 이동 로직 (동적 층수 반영)
        if mode == 'morning':
            if r < 0.85: # 거주층 -> 1층/지하
                start_idx = random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
                end_idx = random.randint(0, f1_idx)
            else:
                start_idx = random.randint(0, total_fs - 1)
                end_idx = random.randint(0, total_fs - 1)
        elif mode == 'evening':
            if r < 0.85: # 1층/지하 -> 거주층
                start_idx = random.randint(0, f1_idx)
                end_idx = random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
            else:
                start_idx = random.randint(0, total_fs - 1)
                end_idx = random.randint(0, total_fs - 1)
        else:
            start_idx = random.randint(0, total_fs - 1)
            end_idx = random.randint(0, total_fs - 1)

        if start_idx == end_idx: continue

        # 엘리베이터 배정 및 시간 계산
        dist_a = abs(pos_a - start_idx)
        dist_b = abs(pos_b - start_idx)
        chosen_dist = min(dist_a, dist_b)
        
        if dist_a <= dist_b: pos_a = end_idx
        else: pos_b = end_idx

        travel_dist = abs(start_idx - end_idx)
        total_time = (chosen_dist * TIME_PER_FLOOR) + DOOR_CYCLE + (travel_dist * TIME_PER_FLOOR) + DOOR_CYCLE
        
        # 결과 기록
        if is_res(start_idx, f1_idx) and is_1f(end_idx, f1_idx): stats['resTo1F'].append(total_time)
        if is_1f(start_idx, f1_idx) and is_res(end_idx, f1_idx): stats['f1ToRes'].append(total_time)
        if is_res(start_idx, f1_idx) and is_b(end_idx, f1_idx): stats['resToB'].append(total_time)

    return {k: (sum(v)/len(v) if v else 0) for k, v in stats.items()}

# ----------------- MAIN LAYOUT -----------------
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Building Status")
    # 설정된 층수에 따라 시각화 자동 생성
    for floor in reversed(FLOOR_LABELS):
        is_idle = (floor == idle_a or floor == idle_b)
        st.markdown(f"""<div style="background:#1e293b; padding:2px 10px; margin:1px; border-radius:3px; font-size:10px; border-left: 4px solid {'#10b981' if is_idle else '#334155'}">
            {floor} {'🟢' if floor == idle_a else ''} {'🟣' if floor == idle_b else ''}</div>""", unsafe_allow_html=True)

with col2:
    st.subheader("📊 시뮬레이션 결과")
    if run_btn:
        res = run_simulation(current_mode, FLOOR_LABELS.index(idle_a), FLOOR_LABELS.index(idle_b), idx_1f, TOTAL_FLOORS)
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.metric("상행 (1층→거주층)", f"{res['f1ToRes']:.1f}초")
            st.metric("하행 (거주층→1층)", f"{res['resTo1F']:.1f}초")
        with col_res2:
            st.metric("주차장 (거주층→지하)", f"{res['resToB']:.1f}초")
            st.info(f"설정된 총 층수: {TOTAL_FLOORS}개 층")
    else:
        st.write("왼쪽에서 층수를 정한 뒤 실행 버튼을 누르세요.")
