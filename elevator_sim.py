import streamlit as st
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Custom Arena Simulator Pro", layout="wide")

st.title("🏢 Advanced Elevator Simulator Pro")
st.caption("기계 성능(속도, 문 개폐 시간) 및 다중 엘리베이터 최적화 시뮬레이션")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 장비 설정")
    max_f = st.number_input("최고 층 (지상)", min_value=1, max_value=100, value=30)
    min_f = st.number_input("최저 층 (지하)", min_value=0, max_value=20, value=5)
    num_elevators = st.slider("엘리베이터 개수", min_value=1, max_value=10, value=2)
    
    st.divider()
    
    st.header("⚡ 엘리베이터 성능 설정")
    # 사용자가 직접 시간을 조정하는 부분
    sec_per_floor = st.number_input("한 층 이동 시간 (초)", min_value=0.1, max_value=10.0, value=2.5, step=0.1)
    door_time = st.number_input("문 개폐 사이클 시간 (초)", min_value=1.0, max_value=20.0, value=7.0, step=0.5)
    st.info(f"💡 현재 설정: 10층 이동 시 {10 * sec_per_floor:.1f}초 소요")

    st.divider()
    
    st.header("🎯 승객 요구 목표 시간 (초)")
    target_b_res = st.number_input("지하 → 거주층 목표", value=86)
    target_f1res = st.number_input("1층 → 거주층 목표", value=47)
    target_res1f = st.number_input("거주층 → 1층 목표", value=83)
    
    st.divider()
    
    st.header("⚙️ 상황 설정")
    mode_label = st.radio("시간대 선택", ["퇴근 시간", "출근 시간", "그 외 시간"])
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "그 외 시간": "normal"}
    current_mode = mode_map[mode_label]
    
    # 층 레이블 생성
    FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
    TOTAL_FLOORS = len(FLOOR_LABELS)
    idx_1f = min_f

    # 엘리베이터별 대기층 설정
    st.subheader("엘리베이터 대기 전략")
    idle_positions = []
    cols = st.columns(2)
    for i in range(num_elevators):
        with cols[i % 2]:
            pos = st.selectbox(f"Elev {chr(65+i)} 대기", options=FLOOR_LABELS, index=idx_1f if i == 0 else 0)
            idle_positions.append(FLOOR_LABELS.index(pos))
    
    run_btn = st.button("시뮬레이션 실행", type="primary", use_container_width=True)

# ----------------- SIMULATION ENGINE -----------------
def run_simulation(mode, idles, f1_idx, total_fs, s_per_f, d_time):
    stats = {'resTo1F': [], 'f1ToRes': [], 'bToRes': []}
    num_trips = 1500
    elevator_positions = list(idles)

    for _ in range(num_trips):
        r = random.random()
        # 승객 동선 결정 로직
        if mode == 'evening':
            if r < 0.70:
                start_idx, end_idx = f1_idx, random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
            elif r < 0.90:
                start_idx, end_idx = random.randint(0, max(0, f1_idx - 1)), random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
            else:
                start_idx, end_idx = random.randint(0, total_fs - 1), random.randint(0, total_fs - 1)
        else:
            start_idx, end_idx = random.randint(0, total_fs - 1), random.randint(0, total_fs - 1)

        if start_idx == end_idx: continue

        # 가장 가까운 엘리베이터 배정
        distances = [abs(pos - start_idx) for pos in elevator_positions]
        chosen_idx = distances.index(min(distances))
        
        # 입력받은 's_per_f'와 'd_time'을 연산에 직접 사용
        wait_time = min(distances) * s_per_f
        travel_time = abs(start_idx - end_idx) * s_per_f
        # 총 시간 = 대기 이동 + 문 열림(출발층) + 주행 이동 + 문 열림(도착층)
        total_time = wait_time + travel_time + (d_time * 2)
        
        elevator_positions[chosen_idx] = end_idx
        
        # 결과 분류
        if start_idx < f1_idx and end_idx > f1_idx + 4: stats['bToRes'].append(total_time)
        elif start_idx == f1_idx and end_idx > f1_idx + 4: stats['f1ToRes'].append(total_time)
        elif start_idx > f1_idx + 4 and end_idx == f1_idx: stats['resTo1F'].append(total_time)

    return {k: (sum(v)/len(v) if v else 0) for k, v in stats.items()}

# ----------------- DISPLAY RESULTS -----------------
col_b, col_r = st.columns([1, 2])

with col_b:
    st.subheader("🏢 건물 모니터링")
    for floor in reversed(FLOOR_LABELS):
        f_idx = FLOOR_LABELS.index(floor)
        elev_icons = "".join([f" 🤖{chr(65+i)}" for i, p in enumerate(idle_positions) if f_idx == p])
        bg = "#1e293b" if f_idx >= idx_1f else "#0f172a"
        st.markdown(f"""<div style="background:{bg}; padding:1px 10px; margin:1px; border-radius:3px; font-size:11px; border-left: 5px solid {'#4f46e5' if elev_icons else '#334155'}">
            {floor} <span style="color:#818cf8">{elev_icons}</span></div>""", unsafe_allow_html=True)

with col_r:
    st.subheader("📊 성능 분석 결과")
    if run_btn:
        res = run_simulation(current_mode, idle_positions, idx_1f, TOTAL_FLOORS, sec_per_floor, door_time)
        
        metrics = [
            ("주차장 (지하→거주층)", res['bToRes'], target_b_res),
            ("로비 (1층→거주층)", res['f1ToRes'], target_f1res),
            ("외출 (거주층→1층)", res['resTo1F'], target_res1f)
        ]

        for label, actual, target in metrics:
            diff = actual - target
            is_ok = actual <= target
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric(label=label, value=f"{actual:.1f}초", 
                          delta=f"{diff:+.1f}초 (목표 대비)", 
                          delta_color="normal" if is_ok else "inverse")
            with c2:
                st.progress(min(actual / target, 1.2) / 1.2)
                if is_ok: st.success(f"✅ 목표 달성 (목표: {target}s)")
                else: st.error(f"⚠️ 지연 발생 (목표: {target}s)")
            st.divider()
    else:
        st.info("왼쪽 사이드바에서 기계 성능을 조절한 뒤 실행해 보세요!")
