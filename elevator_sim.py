import streamlit as st
import random
import pandas as pd

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Advanced Arena Simulator", layout="wide")

st.title("🏢 Advanced Arena Simulator")
st.caption("건물 규모, 엘리베이터 개수, 목표 시간 대비 성능 분석 시뮬레이션")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 장비 설정")
    max_f = st.number_input("최고 층 (지상)", min_value=1, max_value=100, value=30)
    min_f = st.number_input("최저 층 (지하)", min_value=0, max_value=20, value=5)
    num_elevators = st.slider("엘리베이터 개수", min_value=1, max_value=10, value=2)
    
    # 층 레이블 생성 및 1층 위치 파악
    FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
    TOTAL_FLOORS = len(FLOOR_LABELS)
    idx_1f = min_f

    st.divider()
    
    st.header("🎯 승객 요구 목표 시간 (초)")
    target_res1f = st.number_input("거주층 → 1층 목표", value=83)
    target_f1res = st.number_input("1층 → 거주층 목표", value=47)
    target_res_b = st.number_input("거주층 → 지하 목표", value=75)
    
    st.divider()
    
    st.header("⚙️ 상황 설정")
    mode_label = st.radio("시간대 선택", ["출근 시간", "퇴근 시간", "그 외 시간"])
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "그 외 시간": "normal"}
    current_mode = mode_map[mode_label]
    
    # 엘리베이터별 대기층 설정 (개수에 따라 동적 생성)
    st.subheader("엘리베이터 대기 전략")
    idle_positions = []
    cols = st.columns(2)
    for i in range(num_elevators):
        with cols[i % 2]:
            pos = st.selectbox(f"Elev {chr(65+i)} 대기", options=FLOOR_LABELS, index=idx_1f if i == 0 else TOTAL_FLOORS-1)
            idle_positions.append(FLOOR_LABELS.index(pos))
    
    run_btn = st.button("시뮬레이션 실행", type="primary", use_container_width=True)

# ----------------- SIMULATION ENGINE -----------------
TIME_PER_FLOOR = 2.5
DOOR_CYCLE = 7.0

def is_res(idx, f1_idx): return idx > f1_idx + 4
def is_b(idx, f1_idx): return idx < f1_idx
def is_1f(idx, f1_idx): return idx == f1_idx

def run_simulation(mode, idles, f1_idx, total_fs):
    stats = {'resTo1F': [], 'f1ToRes': [], 'resToB': []}
    num_trips = 1500
    # 여러 대의 엘리베이터 위치 관리
    elevator_positions = list(idles)

    for _ in range(num_trips):
        # 1. 승객 발생 (모드별 로직)
        r = random.random()
        if mode == 'morning':
            if r < 0.85:
                start_idx = random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
                end_idx = random.randint(0, f1_idx)
            else:
                start_idx = random.randint(0, total_fs - 1)
                end_idx = random.randint(0, total_fs - 1)
        elif mode == 'evening':
            if r < 0.85:
                start_idx = random.randint(0, f1_idx)
                end_idx = random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
            else:
                start_idx = random.randint(0, total_fs - 1)
                end_idx = random.randint(0, total_fs - 1)
        else:
            start_idx = random.randint(0, total_fs - 1)
            end_idx = random.randint(0, total_fs - 1)

        if start_idx == end_idx: continue

        # 2. 가장 가까운 엘리베이터 찾기 (멀티 엘리베이터 로직)
        distances = [abs(pos - start_idx) for pos in elevator_positions]
        min_dist = min(distances)
        chosen_idx = distances.index(min_dist)
        
        # 3. 시간 계산 (대기 시간 + 이동 시간 + 도어 2회)
        travel_dist = abs(start_idx - end_idx)
        wait_time = min_dist * TIME_PER_FLOOR
        travel_time = travel_dist * TIME_PER_FLOOR
        total_time = wait_time + travel_time + (DOOR_CYCLE * 2)
        
        # 혼잡도 정지 페널티 (엘리베이터가 적을수록 정지 횟수 증가 확률 반영)
        stops = random.randint(0, 2) if num_elevators < 3 else random.randint(0, 1)
        total_time += stops * 6.0

        # 4. 엘리베이터 위치 업데이트 및 통계 기록
        elevator_positions[chosen_idx] = end_idx
        
        if is_res(start_idx, f1_idx) and is_1f(end_idx, f1_idx): stats['resTo1F'].append(total_time)
        elif is_1f(start_idx, f1_idx) and is_res(end_idx, f1_idx): stats['f1ToRes'].append(total_time)
        elif is_res(start_idx, f1_idx) and is_b(end_idx, f1_idx): stats['resToB'].append(total_time)

        # 15% 확률로 유휴 상태 시 설정된 대기층으로 복귀
        if random.random() < 0.15:
            elevator_positions = list(idles)

    return {k: (sum(v)/len(v) if v else 0) for k, v in stats.items()}

# ----------------- DISPLAY RESULTS -----------------
col_b, col_r = st.columns([1, 2])

with col_b:
    st.subheader("🏢 건물 모니터링")
    for floor in reversed(FLOOR_LABELS):
        f_idx = FLOOR_LABELS.index(floor)
        elev_icons = ""
        for i, idle_p in enumerate(idle_positions):
            if f_idx == idle_p: elev_icons += f" 🤖{chr(65+i)}"
        
        bg = "#1e293b" if f_idx >= idx_1f else "#0f172a"
        st.markdown(f"""<div style="background:{bg}; padding:1px 10px; margin:1px; border-radius:3px; font-size:11px; border-left: 5px solid {'#4f46e5' if elev_icons else '#334155'}">
            {floor} <span style="color:#818cf8">{elev_icons}</span></div>""", unsafe_allow_html=True)

with col_r:
    st.subheader("📊 목표 시간 대비 성능 분석")
    if run_btn:
        res = run_simulation(current_mode, idle_positions, idx_1f, TOTAL_FLOORS)
        
        metrics = [
            ("상행 (1층→거주층)", res['f1ToRes'], target_f1res, "저녁 퇴근 시 주로 발생"),
            ("하행 (거주층→1층)", res['resTo1F'], target_res1f, "아침 출근 시 주로 발생"),
            ("주차장 (거주층→지하)", res['resToB'], target_res_b, "자차 이용 승객 이동")
        ]
        
        # 퇴근 시간일 경우 상행을 맨 위로 (이전 요청 반영)
        if current_mode == "evening":
            metrics = [metrics[0], metrics[1], metrics[2]]
        else:
            metrics = [metrics[1], metrics[0], metrics[2]]

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
                # 차이 분석 그래프 (목표 대비 달성률)
                perf_pct = min(actual / target, 2.0)
                st.progress(perf_pct / 2.0 if not is_ok else actual / target / 2.0)
                if is_ok: st.success(f"✅ 목표 달성! ({abs(diff):.1f}초 단축)")
                else: st.error(f"⚠️ 목표 초과 ({diff:.1f}초 지연)")
            st.divider()
    else:
        st.info("왼쪽 설정을 확인하고 [시뮬레이션 실행] 버튼을 눌러주세요.")
