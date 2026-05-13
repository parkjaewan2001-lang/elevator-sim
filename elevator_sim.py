import streamlit as st
import random

# ----------------- STREAMLIT UI SETTINGS -----------------
st.set_page_config(page_title="Advanced Elevator Simulator Pro", layout="wide")

st.title("🏢 Advanced Elevator Simulator Pro")
st.caption("건물 규모, 기계 성능 및 시간대별 승객 유입 비율 조정 시뮬레이션")

# ----------------- SIDEBAR: CONFIGURATION -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 장비 설정")
    max_f = st.number_input("최고 층 (지상)", min_value=1, max_value=100, value=30)
    min_f = st.number_input("최저 층 (지하)", min_value=0, max_value=20, value=5)
    num_elevators = st.slider("엘리베이터 개수", min_value=1, max_value=10, value=2)
    
    st.divider()
    
    st.header("⚡ 엘리베이터 성능 설정")
    sec_per_floor = st.number_input("한 층 이동 시간 (초)", min_value=0.1, max_value=10.0, value=2.5, step=0.1)
    door_time = st.number_input("문 개폐 사이클 시간 (초)", min_value=1.0, max_value=20.0, value=7.0, step=0.5)

    st.divider()
    
    st.header("⚙️ 상황 및 비율 설정")
    mode_label = st.radio("시간대 선택", ["출근 시간", "퇴근 시간", "그 외 시간"])
    mode_map = {"출근 시간": "morning", "퇴근 시간": "evening", "그 외 시간": "normal"}
    current_mode = mode_map[mode_label]

    if current_mode == "morning":
        st.subheader("🌅 출근 목적지 비율")
        morning_dest_ratio = st.slider("1층 하행 vs 지하 하행", 0, 100, 70, help="높을수록 1층으로 가는 인원이 많아집니다.")
        st.write(f"1층행: {morning_dest_ratio}% / 지하행: {100-morning_dest_ratio}%")
    elif current_mode == "evening":
        st.subheader("🌇 퇴근 출발지 비율")
        evening_start_ratio = st.slider("1층 상행 vs 지하 상행", 0, 100, 70, help="높을수록 1층에서 탑승하는 인원이 많아집니다.")
        st.write(f"1층 출발: {evening_start_ratio}% / 지하 출발: {100-evening_start_ratio}%")

    st.divider()
    
    st.header("🎯 승객 요구 목표 시간 (초)")
    target_res_b = st.number_input("거주층 ↔ 지하 목표", value=75)
    target_res1f = st.number_input("거주층 ↔ 1층 목표", value=83)
    target_f1res = st.number_input("1층 ↔ 거주층 목표", value=47)
    
    FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
    TOTAL_FLOORS = len(FLOOR_LABELS)
    idx_1f = min_f

    st.subheader("엘리베이터 대기 전략")
    idle_positions = []
    cols = st.columns(2)
    for i in range(num_elevators):
        with cols[i % 2]:
            pos = st.selectbox(f"Elev {chr(65+i)} 대기", options=FLOOR_LABELS, index=idx_1f if i == 0 else 0)
            idle_positions.append(FLOOR_LABELS.index(pos))
    
    run_btn = st.button("시뮬레이션 실행", type="primary", use_container_width=True)

# ----------------- SIMULATION ENGINE -----------------
def run_simulation(mode, idles, f1_idx, total_fs, s_per_f, d_time, ratio):
    stats = {'resTo1F': [], 'f1ToRes': [], 'resToB': [], 'bToRes': []}
    num_trips = 1500
    elevator_positions = list(idles)

    for _ in range(num_trips):
        r = random.random()
        ratio_f = ratio / 100.0

        if mode == 'morning':
            if r < 0.85: # 출근 하행 집중
                start_idx = random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
                # 사용자가 설정한 비율에 따라 목적지 결정
                if random.random() < ratio_f:
                    end_idx = f1_idx # 1층행
                else:
                    end_idx = random.randint(0, max(0, f1_idx - 1)) # 지하행
            else:
                start_idx, end_idx = random.randint(0, total_fs - 1), random.randint(0, total_fs - 1)
        
        elif mode == 'evening':
            if r < 0.85: # 퇴근 상행 집중
                # 사용자가 설정한 비율에 따라 출발지 결정
                if random.random() < ratio_f:
                    start_idx = f1_idx # 1층 출발
                else:
                    start_idx = random.randint(0, max(0, f1_idx - 1)) # 지하 출발
                end_idx = random.randint(min(f1_idx + 5, total_fs-1), total_fs - 1)
            else:
                start_idx, end_idx = random.randint(0, total_fs - 1), random.randint(0, total_fs - 1)
        else:
            start_idx, end_idx = random.randint(0, total_fs - 1), random.randint(0, total_fs - 1)

        if start_idx == end_idx: continue

        distances = [abs(pos - start_idx) for pos in elevator_positions]
        chosen_idx = distances.index(min(distances))
        
        wait_time = min(distances) * s_per_f
        travel_time = abs(start_idx - end_idx) * s_per_f
        total_time = wait_time + travel_time + (d_time * 2)
        
        elevator_positions[chosen_idx] = end_idx
        
        # 통계 기록
        if start_idx > f1_idx + 4 and end_idx == f1_idx: stats['resTo1F'].append(total_time)
        elif start_idx > f1_idx + 4 and end_idx < f1_idx: stats['resToB'].append(total_time)
        elif start_idx == f1_idx and end_idx > f1_idx + 4: stats['f1ToRes'].append(total_time)
        elif start_idx < f1_idx and end_idx > f1_idx + 4: stats['bToRes'].append(total_time)

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
    mode_title = "출근 시간" if current_mode == "morning" else "퇴근 시간" if current_mode == "evening" else "일반 시간"
    st.subheader(f"📊 {mode_title} 분석 결과")
    
    if run_btn:
        active_ratio = morning_dest_ratio if current_mode == "morning" else evening_start_ratio if current_mode == "evening" else 50
        res = run_simulation(current_mode, idle_positions, idx_1f, TOTAL_FLOORS, sec_per_floor, door_time, active_ratio)
        
        # 모드별 결과 표시 순서 최적화
        if current_mode == "morning":
            metrics = [
                ("하행 (거주층→1층)", res['resTo1F'], target_res1f),
                ("하행 (거주층→지하)", res['resToB'], target_res_b),
                ("상행 (1층→거주층)", res['f1ToRes'], target_f1res)
            ]
        else:
            metrics = [
                ("상행 (1층→거주층)", res['f1ToRes'], target_f1res),
                ("상행 (지하→거주층)", res['bToRes'], target_res_b),
                ("하행 (거주층→1층)", res['resTo1F'], target_res1f)
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
                st.progress(min(actual / target, 1.5) / 1.5)
                if is_ok: st.success(f"✅ 목표 달성 (목표: {target}s)")
                else: st.error(f"⚠️ 지연 발생 (목표: {target}s)")
            st.divider()
    else:
        st.info("비율을 조정한 뒤 시뮬레이션 버튼을 눌러주세요.")
