import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] UI 및 페이지 전역 설정 -----------------
st.set_page_config(page_title="Elevator ESG & SLA Lab", layout="wide")
st.title("🏢 Elevator Strategic, ESG & SLA Experiment Lab")
st.subheader("⚡ 동선별 타임라인·SLA 달성률 및 회생제동 기반 에너지/탄소 통합 추적 시스템")

st.markdown("""
> 💡 **Simulation Methodology (연구 방법론):**
> * **개별 동선 추적:** 4개 동선(1층↔거주층, 주차장↔거주층)의 실시간 소요 시간과 개별 SLA 달성률을 정밀 모니터링합니다.
> * **표준 물리 참조 및 회생제동 모델:** 기어리스 동기모터(Efficiency 85%) 및 KEPCO 종합계약 단가 기준. 특히 신축 아파트 필수 기술인 **회생 제동(Regenerative Braking)** 물리 공식과 **포아송 분포 트래픽**을 반영합니다.
> * **🤖 Q-Learning (강화학습) 추가:** 선택된 시간대의 트래픽 패턴을 기반으로 엘리베이터 에이전트가 3,000회 자체 학습하여 최적의 무부하 대기 위치(Idle Floor)를 스스로 도출합니다.
""")

# ----------------- [2] SIDEBAR: 설정 변수 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 설정")
    c1, c2 = st.columns(2)
    with c1:
        max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2:
        min_f = st.number_input("지하 최저층", value=5, step=1)
    
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10)
    households_per_floor = st.number_input("층당 세대수 (가구)", value=4, min_value=1)
    stairs_floor = st.number_input("계단 이용 권장 층수", value=3, min_value=0, max_value=max_f)
    parking_usage_rate = st.number_input("🚗 주차장 이용 비율 (%)", value=30, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("📊 통계적 트래픽 및 층별 가중치")
    poisson_lambda = st.number_input(
        "포아송 분포 λ (분당 호출 집중도)", 
        min_value=1.0, max_value=20.0, value=7.5, step=0.5
    )
    high_floor_penalty = st.number_input(
        "고층부 대기 패널티 계수", 
        min_value=1.0, max_value=3.0, value=1.5, step=0.1
    )

    st.divider()
    st.header("🌱 ESG 하드웨어 옵션")
    regen_enabled = st.toggle("🔄 회생제동(Regen) 인버터 활성화", value=True)

    st.divider()
    st.header("🚀 물리 엔진 설정")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)
    
    fixed_door_moving_time = st.number_input("고정 기계 작동 시간 (초)", value=4.0, min_value=1.0, step=0.5)
    base_door_time = st.number_input("기본 전체 문 시간 (초)", value=7.0, min_value=fixed_door_moving_time + 0.5, step=0.5)
    button_efficiency = st.number_input("🔘 닫힘 버튼 효율 (%)", value=40, min_value=0, max_value=100, step=5)
    
    st.divider()
    st.header("⚠️ 서비스 임계치 (SLA) 설정")
    lim_1f_up = st.number_input("SLA: 1층 → 거주층 (초)", value=45, min_value=10)
    lim_res_1f = st.number_input("SLA: 거주층 → 1층 (초)", value=55, min_value=10)
    lim_p_up = st.number_input("SLA: 주차장 → 거주층 (초)", value=50, min_value=10)
    lim_res_p = st.number_input("SLA: 거주층 → 주차장 (초)", value=65, min_value=10)

# ----------------- [3] 건물 기초 배열 및 물리 엔진 코어 -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f 
total_fs = len(FLOOR_LABELS)
mid_idx = (total_fs + idx_1f) // 2

def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel: 
        return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route_esg_sla(start, end, placements, logic, cong, is_deliv, eff, base_t, fixed_t, p_rate, s_floor, households, is_regen_on, p_lambda, h_penalty, start_idx, tot_floors):
    if abs(start - end) <= s_floor and start >= start_idx:
        return 5.0, 0.001
    
    congestion_weights = {"매우 쾌적": 0.7, "쾌적": 0.9, "보통": 1.1, "혼잡": 1.8, "매우 혼잡": 2.5}
    h_weight = 1.0 + (households - 1) * 0.05
    w = congestion_weights[cong] * h_weight
    if is_deliv: w = w * 1.5
    
    avail = [i for i in range(num_elevators)]
    if num_elevators > 1:
        if "홀짝" in logic:
            avail = [i for i in avail if start <= start_idx or (i % 2 == 0 and start % 2 != 0) or (i % 2 != 0 and start % 2 == 0)]
        elif "분할" in logic:
            mid = (tot_floors + start_idx) // 2
            avail = [i for i in avail if start <= start_idx or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid)]
    if not avail: avail = [0]
    
    chosen_el_idx = avail[0]
    min_dist_m = abs(placements[chosen_el_idx] - start) * floor_height
    wait_t = get_phys_time(min_dist_m, max_velocity, acceleration)
    
    if logic == "베이스 스테이션 집중" and start != start_idx:
        min_dist_m += (abs(end - start_idx) * floor_height) 

    w_floor = 1.0 + ((start - start_idx) / (tot_floors - start_idx)) * h_penalty if start > start_idx else 1.0
    poisson_multiplier = 1.0 + (np.random.poisson(p_lambda) * 0.05) 
    wait_t = wait_t * w_floor * poisson_multiplier

    move_dist_m = abs(start - end) * floor_height
    move_t = get_phys_time(move_dist_m, max_velocity, acceleration)
    
    if start < start_idx or end < start_idx: wait_t = wait_t * (1 - (p_rate / 100) * 0.4)
    
    pure_dwell = max(0.0, base_t - fixed_t)
    door_eff_t = fixed_t + (pure_dwell * (1 - (eff/100)))
    if start == start_idx: door_eff_t = door_eff_t * 1.2
        
    final_time = (wait_t + move_t + (door_eff_t * w)) * (1.3 if is_deliv else 1.0)
    total_moving_dist = min_dist_m + move_dist_m
    moving_time_pure = get_phys_time(total_moving_dist, max_velocity, acceleration)
    energy_move_base = ((500 * 9.8 * max_velocity * moving_time_pure) / (0.85 * 3600 * 1000)) * (2.4 if is_deliv else 1.0)
    
    regen_factor = 1.0
    is_upward = (end > start)
    is_heavy_load = (w >= 1.2 or is_deliv)
    if is_regen_on:
        if is_upward and not is_heavy_load: regen_factor = -0.35
        elif not is_upward and is_heavy_load: regen_factor = -0.40
        elif is_upward and is_heavy_load: regen_factor = 1.30
    else:
        regen_factor = 1.30 if is_upward and is_heavy_load else 1.05
        
    energy_door = 0.001 * w * (1.8 if is_deliv else 1.0)
    total_kwh = (energy_move_base * regen_factor) + energy_door
    
    return final_time, total_kwh

# ----------------- [4] MAIN UI 및 전략 세팅 (강화학습 포함) -----------------
st.header("⚙️ 시뮬레이션 타임라인 및 수동 배치 설정")
st.info(f"📍 **건물 구조 분석:** 총 {total_fs}개 층 (지하 {min_f}개 층 ~ 지상 {max_f}개 층) ｜ 🏢 **현재 고층부 기준:** **{FLOOR_LABELS[mid_idx]} 이상**")

c_time, c_custom = st.columns([1, 1])

with c_time:
    st.write("##### ⏰ 시간대 및 외부 환경 선택")
    time_options = [
        "새벽 시간 (00시~06시) [경부하]", "출근 시간 (07시~09시) [최대부하]", 
        "낮 시간 (09시~18시) [중부하]", "퇴근 시간 (18시~20시) [최대부하]", 
        "저녁 시간 (20시~23시) [최대부하]"
    ]
    mode_selection = st.radio("시간대 패턴 선택", options=time_options, index=1, horizontal=False)
    mode_index = time_options.index(mode_selection)
    mode_label = mode_selection.split(" (")[0]
    current_is_deliv = True if mode_index == 0 else False
    
    if "경부하" in mode_selection: kepco_rate = 78.0
    elif "중부하" in mode_selection: kepco_rate = 132.0
    else: kepco_rate = 195.0

with c_custom:
    st.write("##### ✍️ 사용자 수동 배치 설정")
    m_cols = st.columns(num_elevators)
    manual_placements = []
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f, key=f"v_percent_{i}")
            manual_placements.append(val)

st.divider()

# --- 🧠 Q-Learning 에이전트 학습 과정 ---
@st.cache_data
def train_rl_agent(m_idx, t_fs, i_1f, p_rate, num_el, epochs=3000):
    q_table = np.zeros(t_fs)
    history = []
    alpha, gamma = 0.1, 0.9
    
    for ep in range(epochs):
        epsilon = max(0.05, 0.5 * (1 - ep/epochs))
        action = np.random.randint(0, t_fs) if np.random.rand() < epsilon else np.argmax(q_table)
        
        # 시간대별 승객 발생 시나리오
        if m_idx == 0: start_f = i_1f
        elif m_idx == 1: start_f = np.random.randint(i_1f + 1, t_fs)
        elif m_idx == 2: start_f = np.random.randint(i_1f, t_fs)
        elif m_idx == 3: start_f = np.random.randint(0, i_1f) if (np.random.rand() < p_rate/100 and i_1f > 0) else i_1f
        else: start_f = i_1f
        
        # 보상 산출 (물리적 이동거리 페널티 + 약간의 랜덤 노이즈)
        dist_penalty = abs(action - start_f)
        reward = -dist_penalty 
        
        q_table[action] = q_table[action] + alpha * (reward + gamma * np.max(q_table) - q_table[action])
        
        if ep % 100 == 0:
            history.append(np.mean(q_table))
            
    # 가장 Q값이 높은 위치 N개 추출
    best_floors = np.argsort(q_table)[-num_el:]
    return list(best_floors), history

rl_placements, rl_history = train_rl_agent(mode_index, total_fs, idx_1f, parking_usage_rate, num_elevators)

with st.expander("🤖 강화학습(Q-Learning) 에이전트 학습 리포트 열기"):
    st.write(f"**현재 시간대({mode_label})**의 승객 패턴을 에이전트가 3,000번 가상 플레이하며 최적의 대기 층을 스스로 도출했습니다.")
    st.success(f"🎓 **에이전트가 찾아낸 엘리베이터 대기 명당:** **{[FLOOR_LABELS[f] for f in rl_placements]}**")
    st.line_chart(pd.DataFrame({"학습 에피소드 (x100)": range(len(rl_history)), "평균 보상 점수(Loss 수렴)": rl_history}), x="학습 에피소드 (x100)", y="평균 보상 점수(Loss 수렴)")

# --- 전략 세팅 맵 ---
strategies_config = {}
np.random.seed(42) 

strategies_config["전략 미적용 (랜덤 운행)"] = {"placements": list(np.random.randint(0, total_fs, num_elevators)), "logic": "자유 운행"}

strategies_config["🤖 RL 강화학습 에이전트"] = {"placements": rl_placements, "logic": "자유 운행"}

split_placements = [int(idx_1f + (mid_idx-idx_1f)/2) if i < num_elevators/2 else int(mid_idx + (total_fs-mid_idx)/2) for i in range(num_elevators)] if num_elevators > 1 else [mid_idx]
strategies_config["고층부/저층부 분할배치"] = {"placements": split_placements, "logic": "분할 배치"}

strategies_config["베이스 스테이션 집중"] = {"placements": [idx_1f] * num_elevators, "logic": "자유 운행"}

if mode_index == 0: ai_pos = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2) if num_elevators > 1 else [idx_1f]
elif mode_index == 1: ai_pos = [int(idx_1f + stairs_floor + 1 + (total_fs - 1 - (idx_1f + stairs_floor + 1)) * (i + 1) / (num_elevators + 1)) for i in range(num_elevators)]
elif mode_index == 3: ai_pos = [0] * int(round(num_elevators * (parking_usage_rate / 100))) + [idx_1f] * (num_elevators - int(round(num_elevators * (parking_usage_rate / 100))))
else: ai_pos = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config[f"기존 규칙기반 AI ({mode_label})"] = {"placements": ai_pos, "logic": "자유 운행"}

strategies_config["사용자 수동 배치"] = {"placements": manual_placements, "logic": "자유 운행"}

# ----------------- [5] 시뮬레이션 가동 및 매트릭스 도출 -----------------
st.divider()
st.subheader("🌐 시뮬레이션 환경 조건 가동")
c_env1, c_env2 = st.columns(2)
with c_env1: congestion = st.radio("건물 내부 혼잡도", options=["매우 쾌적", "쾌적", "보통", "혼잡", "매우 혼잡"], index=2, horizontal=True)
with c_env2: delivery_mode = st.toggle("📦 배달 패널티 활성화", value=current_is_deliv)

if st.button("🚀 전체 전략 통합 시뮬레이션 실행", type="primary", use_container_width=True):
    avg_res_f = int(idx_1f + (max_f - 1) * 0.7)
    scenarios = {
        "1층 ⬆️ 거주층": (idx_1f, avg_res_f, lim_1f_up),
        "거주층 ⬇️ 1층": (avg_res_f, idx_1f, lim_res_1f),
        "주차장 ⬆️ 거주층": (0, avg_res_f, lim_p_up),
        "거주층 ⬇️ 주차장": (avg_res_f, 0, lim_res_p)
    }
    
    matrix_results = []
    
    for s_name, (start, end, target_sla) in scenarios.items():
        for strat_name, config in strategies_config.items():
            eff_param = button_efficiency if strat_name != "전략 미적용 (랜덤 운행)" else 0
            p_rate_param = parking_usage_rate if strat_name != "전략 미적용 (랜덤 운행)" else 0
            s_floor_param = stairs_floor if strat_name != "전략 미적용 (랜덤 운행)" else 0
            
            calc_time, calc_kwh = simulate_route_esg_sla(
                start, end, config["placements"], config["logic"], 
                congestion, delivery_mode, eff_param, base_door_time, fixed_door_moving_time,
                p_rate_param, s_floor_param, households_per_floor, regen_enabled,
                poisson_lambda, high_floor_penalty, idx_1f, total_fs
            )
            
            matrix_results.append({
                "운영 전략": strat_name, "동선 시나리오": s_name,
                "실제 소요시간": calc_time, "목표 SLA": target_sla,
                "SLA 달성률": (target_sla / calc_time) * 100 if calc_time > 0 else 100.0,
                "SLA 초과(초)": max(0.0, calc_time - target_sla),
                "전력 소비량(kWh)": calc_kwh, "전기 요금(원)": calc_kwh * kepco_rate, "탄소 배출량(g)": calc_kwh * 424.0
            })
            
    df_matrix = pd.DataFrame(matrix_results)
    
    # 📈 [테이블 출력] 동선별 스코어보드
    st.write("### 📈 [동선별 정밀 스코어보드] 운영 전략 × 시나리오 매트릭스")
    final_rows = []
    for strat_name in strategies_config.keys():
        strat_df = df_matrix[df_matrix["운영 전략"] == strat_name]
        row_data = {"운영 전략": strat_name}
        for _, row in strat_df.iterrows():
            scen = row["동선 시나리오"]
            time_v = row["실제 소요시간"]
            pass_v = row["SLA 달성률"]
            base_time = df_matrix[(df_matrix["운영 전략"] == "전략 미적용 (랜덤 운행)") & (df_matrix["동선 시나리오"] == scen)]["실제 소요시간"].values[0]
            time_diff_pct = ((time_v - base_time) / base_time) * 100
            pct_str = f"({time_diff_pct:+.1f}%)" if strat_name != "전략 미적용 (랜덤 운행)" else "(기준)"
            row_data[f"{scen} (소요시간)"] = f"{time_v:.1f}초 {pct_str}"
            row_data[f"{scen} (달성률)"] = f"{pass_v:.1f}% ({'⭕' if pass_v >= 100.0 else '❌'})"
        final_rows.append(row_data)
        
    ordered_cols = [c for c in final_rows[0].keys() if c != "운영 전략"]
    st.dataframe(pd.DataFrame(final_rows).set_index("운영 전략")[ordered_cols], use_container_width=True)
    
    # 🌿 [테이블 출력] ESG 통합 보드
    st.write("### 🌿 [ESG 친환경 통합 요약] 에너지 및 탄소 배출량 비교")
    df_esg = df_matrix.groupby("운영 전략").sum(numeric_only=True).reset_index()
    base_r = df_esg[df_esg["운영 전략"] == "전략 미적용 (랜덤 운행)"].iloc[0]
    esg_rows = []
    for _, row in df_esg.iterrows():
        strat = row["운영 전략"]
        kwh_v = row["전력 소비량(kWh)"]
        cost_v = row["전기 요금(원)"]
        co2_v = row["탄소 배출량(g)"]
        kwh_pct = ((kwh_v - base_r["전력 소비량(kWh)"]) / base_r["전력 소비량(kWh)"]) * 100 if base_r["전력 소비량(kWh)"] else 0
        pct_str = f" ({kwh_pct:+.1f}%)" if strat != "전략 미적용 (랜덤 운행)" else " (기준)"
        
        esg_rows.append({
            "운영 전략": strat, "총 전력 소비량": f"{kwh_v:.4f} kWh{pct_str}",
            "총 예상 전기요금": f"{cost_v:.1f} 원", "누적 탄소 발자국": f"{co2_v:.1f} g CO₂"
        })
    st.dataframe(pd.DataFrame(esg_rows).set_index("운영 전략"), use_container_width=True)

    # 📊 [시각화] 차트
    st.divider()
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        st.write("##### ⏳ 전략별 실제 소요 시간")
        st.altair_chart(alt.Chart(df_matrix).mark_bar().encode(
            x=alt.X('운영 전략:N', axis=alt.Axis(labels=False)), y=alt.Y('실제 소요시간:Q'),
            color='운영 전략:N', column='동선 시나리오:N'
        ).properties(width=130, height=300))
    with g_col2:
        st.write("##### ⚡ 전략별 총 전력 소비량(kWh)")
        st.altair_chart(alt.Chart(df_esg).mark_bar().encode(
            x=alt.X('운영 전략:N', axis=alt.Axis(labelAngle=-45)), y=alt.Y('전력 소비량(kWh):Q'),
            color=alt.Color('운영 전략:N', legend=None)
        ).properties(height=345), use_container_width=True)
