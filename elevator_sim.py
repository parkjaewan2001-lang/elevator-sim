import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] UI 및 페이지 전역 설정 -----------------
st.set_page_config(page_title="Elevator ESG & SLA Lab", layout="wide")
st.title("🏢 Elevator Strategic, ESG & SLA Experiment Lab")
st.subheader("⚡ 동선별 타임라인·SLA 달성률 및 회생제동 기반 에너지 통합 추적 시스템")

st.markdown("""
> 💡 **Simulation Methodology (연구 방법론):**
> * **개별 동선 추적:** 4개 동선(1층↔거주층, 주차장↔거주층)의 실시간 소요 시간과 개별 SLA 달성률을 정밀 모니터링합니다.
> * **표준 물리 참조 모델:** 신축 아파트 필수 기술인 **회생 제동(Regenerative Braking)** 물리 공식과 **포아송 분포 트래픽**을 반영합니다.
> * **🤖 고도화된 Q-Learning (강화학습):** 실제 물리 엔진(대기 시간+전력 소비)을 보상 함수로 연동하여 15,000회의 에피소드를 거쳐 스스로 최적의 대기 명당을 찾아냅니다.
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
    poisson_lambda = st.number_input("포아송 분포 λ (분당 호출 집중도)", min_value=1.0, max_value=20.0, value=7.5, step=0.5)
    high_floor_penalty = st.number_input("고층부 대기 패널티 계수", min_value=1.0, max_value=3.0, value=1.5, step=0.1)

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
    
    # 가장 가까운 엘리베이터 탐색
    min_dist_m = min([abs(placements[i] - start) * floor_height for i in avail])
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

# ----------------- [4] 환경 변수 세팅 (RL 엔진이 참조할 수 있게 위로 배치) -----------------
st.header("⚙️ 시뮬레이션 타임라인 및 환경 설정")
st.info(f"📍 **건물 구조 분석:** 총 {total_fs}개 층 (지하 {min_f}개 층 ~ 지상 {max_f}개 층) ｜ 🏢 **현재 고층부 기준:** **{FLOOR_LABELS[mid_idx]} 이상**")

c_time, c_env1, c_env2 = st.columns([2, 1, 1])

with c_time:
    time_options = [
        "새벽 시간 (00시~06시)", "출근 시간 (07시~09시)", 
        "낮 시간 (09시~18시)", "퇴근 시간 (18시~20시)", "저녁 시간 (20시~23시)"
    ]
    mode_selection = st.selectbox("⏰ 시간대 패턴 선택", options=time_options, index=1)
    mode_index = time_options.index(mode_selection)
    mode_label = mode_selection.split(" (")[0]
    
    if mode_index == 0: kepco_rate = 78.0
    elif mode_index == 2: kepco_rate = 132.0
    else: kepco_rate = 195.0

with c_env1: 
    congestion = st.selectbox("건물 내부 혼잡도", options=["매우 쾌적", "쾌적", "보통", "혼잡", "매우 혼잡"], index=2)
with c_env2: 
    current_is_deliv = True if mode_index == 0 else False
    delivery_mode = st.toggle("📦 배달 패널티 활성화", value=current_is_deliv)

st.divider()

# --- 🧠 풀옵션 Q-Learning 에이전트 학습 과정 ---
@st.cache_data
def train_rl_agent_advanced(m_idx, t_fs, i_1f, p_rate, num_el, cong, deliv_mode, btn_eff, base_t, fixed_t, s_floor, h_holds, regen, p_lam, h_pen, epochs=15000):
    q_table = np.zeros(t_fs)
    history = []
    alpha, gamma = 0.1, 0.9
    
    for ep in range(epochs):
        # 탐색(Exploration)과 활용(Exploitation) 비율 조절
        epsilon = max(0.01, 0.5 * (1 - ep/(epochs*0.8)))
        action = np.random.randint(0, t_fs) if np.random.rand() < epsilon else np.argmax(q_table)
        
        # 현실적인 시간대별 트래픽 발생 시나리오
        if m_idx == 0: # 새벽: 주로 1층/주차장에서 세대로 올라감
            start_f = i_1f if np.random.rand() > 0.3 else 0
            end_f = np.random.randint(i_1f + 1, t_fs)
        elif m_idx == 1: # 출근: 세대에서 1층/주차장으로 쏟아짐
            start_f = np.random.randint(i_1f + 1, t_fs)
            end_f = i_1f if np.random.rand() > (p_rate/100) else 0
        elif m_idx == 3: # 퇴근: 1층/주차장에서 세대로 올라감
            start_f = 0 if np.random.rand() < (p_rate/100) else i_1f
            end_f = np.random.randint(i_1f + 1, t_fs)
        else: # 낮/저녁: 랜덤 유동
            start_f = np.random.randint(0, t_fs)
            end_f = np.random.randint(0, t_fs)
            if start_f == end_f: end_f = (end_f + 1) % t_fs

        # [핵심] 실제 물리 엔진 가동하여 리워드 산출
        wait_time, energy_kwh = simulate_route_esg_sla(
            start=start_f, end=end_f, placements=[action]*num_el, logic="자유 운행",
            cong=cong, is_deliv=deliv_mode, eff=btn_eff, base_t=base_t, fixed_t=fixed_t,
            p_rate=p_rate, s_floor=s_floor, households=h_holds, is_regen_on=regen,
            p_lambda=p_lam, h_penalty=h_pen, start_idx=i_1f, tot_floors=t_fs
        )
        
        # 보상 함수: 대기 시간이 짧을수록, 전력 소모가 적을수록 높은 점수 (페널티 최소화)
        # 시간은 초 단위(예: 30초), 전력은 kWh 단위(예: 0.05kWh)이므로 스케일링을 위해 에너지에 가중치 100 부여
        reward = - (wait_time * 1.0 + energy_kwh * 100.0)
        
        # Q-Value 업데이트
        q_table[action] = q_table[action] + alpha * (reward + gamma * np.max(q_table) - q_table[action])
        
        if ep % 500 == 0:
            history.append(np.mean(q_table))
            
    # 가장 높은 Q값을 가진 상위 N개 층 반환
    best_floors = np.argsort(q_table)[-num_el:]
    return list(best_floors), history

with st.spinner("🤖 강화학습 에이전트가 15,000회 가상 물리 엔진 환경에서 스스로 학습 중입니다... (약 2~5초 소요)"):
    rl_placements, rl_history = train_rl_agent_advanced(
        mode_index, total_fs, idx_1f, parking_usage_rate, num_elevators,
        congestion, delivery_mode, button_efficiency, base_door_time, fixed_door_moving_time,
        stairs_floor, households_per_floor, regen_enabled, poisson_lambda, high_floor_penalty
    )

with st.expander("🤖 풀옵션 Q-Learning 강화학습 리포트 열기 (클릭)", expanded=True):
    st.write(f"**현재 설정된 {mode_label} 트래픽 패턴과 실제 물리 엔진 패널티**를 연동하여 에이전트가 15,000번 가상 플레이했습니다.")
    st.success(f"🎓 **물리엔진 기반 AI가 찾아낸 최적 대기 명당:** **{[FLOOR_LABELS[f] for f in rl_placements]}**")
    st.line_chart(pd.DataFrame({"학습 구간 (x500 에피소드)": range(len(rl_history)), "평균 보상 점수 (0에 가까울수록 최적화됨)": rl_history}), x="학습 구간 (x500 에피소드)", y="평균 보상 점수 (0에 가까울수록 최적화됨)")

# --- 전략 맵 빌드 ---
strategies_config = {}
np.random.seed(42) 

manual_placements = [idx_1f] * num_elevators # 수동 배치는 공간상 기본값 처리

strategies_config["전략 미적용 (랜덤 운행)"] = {"placements": list(np.random.randint(0, total_fs, num_elevators)), "logic": "자유 운행"}
strategies_config["🤖 고도화 RL 강화학습 에이전트"] = {"placements": rl_placements, "logic": "자유 운행"}

split_placements = [int(idx_1f + (mid_idx-idx_1f)/2) if i < num_elevators/2 else int(mid_idx + (total_fs-mid_idx)/2) for i in range(num_elevators)] if num_elevators > 1 else [mid_idx]
strategies_config["고층부/저층부 분할배치"] = {"placements": split_placements, "logic": "분할 배치"}

strategies_config["베이스 스테이션 집중"] = {"placements": [idx_1f] * num_elevators, "logic": "자유 운행"}

if mode_index == 0: ai_pos = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2) if num_elevators > 1 else [idx_1f]
elif mode_index == 1: ai_pos = [int(idx_1f + stairs_floor + 1 + (total_fs - 1 - (idx_1f + stairs_floor + 1)) * (i + 1) / (num_elevators + 1)) for i in range(num_elevators)]
elif mode_index == 3: ai_pos = [0] * int(round(num_elevators * (parking_usage_rate / 100))) + [idx_1f] * (num_elevators - int(round(num_elevators * (parking_usage_rate / 100))))
else: ai_pos = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config[f"기존 규칙기반 AI ({mode_label})"] = {"placements": ai_pos, "logic": "자유 운행"}

# ----------------- [5] 최종 시뮬레이션 가동 및 매트릭스 도출 -----------------
st.subheader("🌐 전체 전략 대조 시뮬레이션")
if st.button("🚀 통합 시뮬레이션 실행 및 결과 보기", type="primary", use_container_width=True):
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
            eff_param = button_efficiency if "전략 미적용" not in strat_name else 0
            
            calc_time, calc_kwh = simulate_route_esg_sla(
                start, end, config["placements"], config["logic"], 
                congestion, delivery_mode, eff_param, base_door_time, fixed_door_moving_time,
                parking_usage_rate, stairs_floor, households_per_floor, regen_enabled,
                poisson_lambda, high_floor_penalty, idx_1f, total_fs
            )
            
            matrix_results.append({
                "운영 전략": strat_name, "동선 시나리오": s_name,
                "실제 소요시간": calc_time, "목표 SLA": target_sla,
                "SLA 달성률": (target_sla / calc_time) * 100 if calc_time > 0 else 100.0,
                "전력 소비량(kWh)": calc_kwh, "전기 요금(원)": calc_kwh * kepco_rate, "탄소 배출량(g)": calc_kwh * 424.0
            })
            
    df_matrix = pd.DataFrame(matrix_results)
    
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
