import streamlit as st
import random
import pandas as pd

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Advanced Arena Simulator", layout="wide")

st.title("🏢 Advanced Arena Simulator")
st.caption("건물 규모, 엘리베이터 개수, 퇴근 동선(지하→거주층) 분석 시뮬레이션")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 장비 설정")
    max_f = st.number_input("최고 층 (지상)", min_value=1, max_value=100, value=30)
    min_f = st.number_input("최저 층 (지하)", min_value=0, max_value=20, value=5)
    num_elevators = st.slider("엘리베이터 개수", min_value=1, max_value=10, value=2)
    
    FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
    TOTAL_FLOORS = len(FLOOR_LABELS)
    idx_1f = min_f

    st.divider()
    
    st.header("🎯 승객 요구 목표 시간 (초)")
    # 요청하신 대로 지하에서 거주층으로 올라가는 방향으로 수정
    target_b_res = st.number_input("지하 → 거주층 목표 (퇴근)", value=86) 
    target_f1res = st.number_input("1층 → 거주층 목표", value=47)
    target_res1f = st.number_input("거주층 → 1층 목표", value=83)
    
    st.divider()
    
    st.header("⚙️ 상황 설정")
    mode_label = st.radio("시간대 선택", ["퇴근 시간", "출근 시간", "그 외 시간"])
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "그 외 시간": "normal"}
    current_mode = mode_map[mode_label]
    
    st.subheader("엘리베이터 대기 전략")
    idle_positions = []
    cols = st.columns(2)
    for i in range(num_elevators):
        with cols[i % 2]:
            pos = st.selectbox(f"Elev {chr(65+i)} 대기", options=FLOOR_LABELS, index=idx_1f if i == 0 else 0)
            idle_positions.append(FLOOR_LABELS.index(pos))
    
    run_btn = st.button("시뮬레이션 실행", type="primary", use_container_width=True)

# ----------------- SIMULATION ENGINE -----------------
TIME_PER_FLOOR = 2.5
DOOR_CYCLE = 7.0

def is_res(idx, f1_idx): return idx > f1_idx + 4
def is_b(idx, f1_idx): return idx < f1_idx
def is_1f(idx, f1_idx): return idx == f1_idx

def run_simulation(mode, idles, f1_idx, total_fs):
    stats = {'resTo1F': [], 'f1ToRes': [], 'bToRes': []} # 지하->거주층(bToRes)으로 변경
    num_trips = 1500
    elevator_positions = list(idles)

    for _ in range(num_trips):
        r = random.random()
        if mode == 'evening':
            if r < 0.70: # 1층 -> 거주층
                start_idx = f1_idx
                end_idx = random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
            elif r < 0.90: # 지하 -> 거주층 (퇴근 시 주차 후 귀가)
                start_idx = random.randint(0, max(0, f1_idx - 1))
                end_idx = random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
            else:
                start_idx = random.randint(0, total_fs - 1)
                end_idx = random.randint(0, total_fs - 1)
        # ... (출근 및 일반 모드 로직은 동일하게 유지)
        else:
            start_idx = random.randint(0, total_fs - 1)
            end_idx = random.randint(0, total_fs - 1)

        if start_idx == end_idx: continue

        distances = [abs(pos - start_idx) for pos in elevator_positions]
        chosen_idx = distances.index(min(distances))
        
        wait_time = min(distances) * TIME_PER_FLOOR
        travel_time = abs(start_idx - end_idx) * TIME_PER_FLOOR
        total_time = wait_time + travel_time + (DOOR_CYCLE * 2)
        
        # 엘리베이터 위치 업데이트
        elevator_positions[chosen_idx] = end_idx
        
        # 통계 분류 수정
        if is_b(start_idx, f1_idx) and is_res(end_idx, f1_idx): stats['bToRes'].append(total_time)
        elif is_1f(start_idx, f1_idx) and is_res(end_idx, f1_idx): stats['f1ToRes'].append(total_time)
        elif is_res(start_idx, f1_idx) and is_1f(end_idx, f1_idx): stats['resTo1F'].append(total_time)

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
    st.subheader("📊 퇴근 시간 분석 결과")
    if run_btn:
        res = run_simulation(current_mode, idle_positions, idx_1f, TOTAL_FLOORS)
        
        # 순서 및 라벨 변경: 지하 -> 거주층을 우선적으로 배치
        metrics = [
            ("주차장 (지하→거주층)", res['bToRes'], target_b_res, "퇴근 후 주차장에서 집으로 이동"),
            ("로비 (1층→거주층)", res['f1ToRes'], target_f1res, "대중교통 이용 후 귀가"),
            ("외출 (거주층→1층)", res['resTo1F'], target_res1f, "저녁 외출 및 배달 이동")
        ]

        for label, actual, target, desc in metrics:
            diff = actual - target
            is_ok = actual <= target
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric(label=label, value=f"{actual:.1f}초", 
                          delta=f"{diff:+.1f}초 (목표: {target}s)", 
                          delta_color="normal" if is_ok else "inverse")
            with c2:
                st.caption(desc)
                perf_pct = min(actual / target, 2.0)
                st.progress(perf_pct / 2.0)
                if is_ok: st.success(f"✅ 목표 달성!")
                else: st.error(f"⚠️ 지연 발생")
            st.divider()
    else:
        st.info("시뮬레이션 실행 버튼을 눌러주세요.")
