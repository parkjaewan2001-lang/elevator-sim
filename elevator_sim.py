import streamlit as st
import random
import pandas as pd

# ----------------- CONSTANTS & HELPERS -----------------
FLOOR_LABELS = [
    'B5', 'B4', 'B3', 'B2', 'B1',
    '1F', '2F', '3F', '4F', '5F', '6F', '7F', '8F', '9F', '10F',
    '11F', '12F', '13F', '14F', '15F', '16F', '17F', '18F', '19F', '20F',
    '21F', '22F', '23F', '24F', '25F', '26F', '27F', '28F', '29F', '30F'
]

TARGETS = {
    'resTo1F': 83,
    'f1ToRes': 47,
    'resToB': 75
}

TIME_PER_FLOOR = 2.5
DOOR_CYCLE = 7.0  # Open 3.5s + Close 3.5s

def is_res(idx): return idx >= 10  # 6F(idx 10) to 30F
def is_b(idx): return 0 <= idx <= 4 # B5 to B1
def is_1f(idx): return idx == 5    # 1F

# ----------------- SIMULATION ENGINE -----------------
def run_simulation(mode, idle_a_idx, idle_b_idx):
    stats = {'resTo1F': [], 'f1ToRes': [], 'resToB': []}
    num_trips = 1500
    
    pos_a = idle_a_idx
    pos_b = idle_b_idx

    for _ in range(num_trips):
        r = random.random()
        start_idx, end_idx = 0, 0

        if mode == 'morning':
            if r < 0.85: # Downward
                start_idx = random.randint(10, 34)
                end_idx = random.randint(0, 4) if random.random() < 0.33 else 5
            elif r < 0.95: # Upward
                start_idx = random.randint(0, 4) if random.random() < 0.33 else 5
                end_idx = random.randint(10, 34)
            else: # Inter-floor
                start_idx = random.randint(10, 34)
                end_idx = random.randint(10, 34)
        elif mode == 'evening':
            if r < 0.85: # Upward (퇴근 시간 집중)
                start_idx = random.randint(0, 4) if random.random() < 0.33 else 5
                end_idx = random.randint(10, 34)
            elif r < 0.95: # Downward
                start_idx = random.randint(10, 34)
                end_idx = random.randint(0, 4) if random.random() < 0.33 else 5
            else:
                start_idx = random.randint(10, 34)
                end_idx = random.randint(10, 34)
        else: # Normal
            start_idx = random.randint(0, 34)
            end_idx = random.randint(0, 34)
            while start_idx == end_idx: end_idx = random.randint(0, 34)

        # Assign closest elevator
        dist_a = abs(pos_a - start_idx)
        dist_b = abs(pos_b - start_idx)
        
        if dist_a <= dist_b:
            chosen_wait_dist = dist_a
            pos_a = end_idx
        else:
            chosen_wait_dist = dist_b
            pos_b = end_idx

        travel_dist = abs(start_idx - end_idx)
        total_time = (chosen_wait_dist * TIME_PER_FLOOR) + DOOR_CYCLE + (travel_dist * TIME_PER_FLOOR) + DOOR_CYCLE
        
        # Stops penalty
        stops = 0
        if mode in ['morning', 'evening']:
            if travel_dist > 12: stops += random.randint(0, 2)
            if chosen_wait_dist > 15: stops += random.randint(1, 3)
            if chosen_wait_dist > 25: stops += random.randint(2, 4)
        elif travel_dist > 15 and random.random() > 0.5:
            stops += 1
        
        total_time += stops * (DOOR_CYCLE * 0.8 + random.uniform(0.5, 2.0))

        if is_res(start_idx) and is_1f(end_idx): stats['resTo1F'].append(total_time)
        if is_1f(start_idx) and is_res(end_idx): stats['f1ToRes'].append(total_time)
        if is_res(start_idx) and is_b(end_idx): stats['resToB'].append(total_time)

        if random.random() < 0.15:
            pos_a, pos_b = idle_a_idx, idle_b_idx

    return {k: (sum(v)/len(v) if v else 0) for k, v in stats.items()}

# ----------------- STREAMLIT UI -----------------
st.set_page_config(page_title="Arena Simulator Pro", layout="wide")

st.title("🏢 Arena Simulator Pro")
st.caption("Virtual Apartment Elevator Strategy Simulation")

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ 시뮬레이션 설정")
    
    mode_label = st.radio(
        "시간대 선택",
        ["출근 시간 (Morning Rush)", "퇴근 시간 (Evening Rush)", "그 외 시간 (Off-peak)"]
    )
    mode_map = {
        "출근 시간 (Morning Rush)": "morning",
        "퇴근 시간 (Evening Rush)": "evening",
        "그 외 시간 (Off-peak)": "normal"
    }
    current_mode = mode_map[mode_label]
    
    st.divider()
    
    st.subheader("대기 층 전략")
    idle_a = st.select_slider("Elevator A 대기 층", options=FLOOR_LABELS, value='15F')
    idle_b = st.select_slider("Elevator B 대기 층", options=FLOOR_LABELS, value='25F')
    
    run_btn = st.button("시뮬레이션 실행", type="primary", use_container_width=True)

# Main Layout
col1, col2, col3 = st.columns([1, 1, 1.5])

with col1:
    st.subheader("Building Status")
    for floor in reversed(FLOOR_LABELS):
        bg_color = "#1e293b"
        label = floor
        indicator = ""
        if floor == idle_a: indicator += "🟢 (A) "
        if floor == idle_b: indicator += "🟣 (B)"
        
        st.markdown(f"""<div style="background:{bg_color}; padding:2px 10px; margin:1px; border-radius:3px; font-size:10px; font-family:monospace; border-left: 4px solid {'#10b981' if indicator else '#334155'}">
            {label} {indicator}</div>""", unsafe_allow_html=True)

with col2:
    st.subheader("시스템 제원")
    st.info("""
    - **규모:** 35층 (B5-30F / 210세대)
    - **이동 속도:** 2.5초 / 층
    - **도어 시간:** 7.0초 (열림+닫힘)
    """)
    st.warning("⚠️ 물리적 거리로 인해 일부 목표 시간은 달성이 어려울 수 있으며, 최적 대기 층을 찾는 것이 목적입니다.")

with col3:
    st.subheader("📊 시뮬레이션 결과")
    
    if run_btn:
        with st.spinner('시뮬레이션 분석 중...'):
            res = run_simulation(current_mode, FLOOR_LABELS.index(idle_a), FLOOR_LABELS.index(idle_b))
            
            def display_metric(label, actual, target, desc):
                diff = actual - target
                color = "normal" if actual <= target else "inverse"
                st.metric(label=label, value=f"{actual:.1f}초", delta=f"{diff:.1f}초 (목표: {target}s)", delta_color=color)
                st.caption(desc)
                progress = min(actual / target, 1.5) / 1.5
                st.progress(progress)
                st.divider()

            # "로직.png" 참고: 퇴근 시간일 경우 순서 변경
            if current_mode == 'evening':
                display_metric("1층 → 거주층 (상행)", res['f1ToRes'], TARGETS['f1ToRes'], "1층에서 주거층으로 올라가는 평균 소요 시간")
                display_metric("거주층 → 1층 (하행)", res['resTo1F'], TARGETS['resTo1F'], "주거층에서 1층으로 이동하는 평균 소요 시간")
                display_metric("거주층 → 지하층", res['resToB'], TARGETS['resToB'], "주거층에서 지하 주차장으로 이동하는 평균 소요 시간")
            else:
                display_metric("거주층 → 1층 (하행)", res['resTo1F'], TARGETS['resTo1F'], "주거층에서 1층으로 이동하는 평균 소요 시간")
                display_metric("1층 → 거주층 (상행)", res['f1ToRes'], TARGETS['f1ToRes'], "1층에서 주거층으로 올라가는 평균 소요 시간")
                display_metric("거주층 → 지하층", res['resToB'], TARGETS['resToB'], "주거층에서 지하 주차장으로 이동하는 평균 소요 시간")
    else:
        st.write("왼쪽 버튼을 눌러 시뮬레이션을 시작하세요.")