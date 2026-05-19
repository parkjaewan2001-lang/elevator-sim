import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] UI 및 페이지 전역 설정 -----------------
st.set_page_config(page_title="Elevator ESG & SLA Lab", layout="wide")
st.title("🏢 Elevator Strategic, ESG & SLA Experiment Lab")
st.subheader("⚡ 동선별 개별 타임라인 및 SLA 달성률 매트릭스 정밀 추적 시스템")

st.markdown("""
> 💡 **Simulation Methodology (연구 방법론):**
> * **개별 동선 추적:** 4개 동선(1층↔거주층, 주차장↔거주층)의 실시간 소요 시간과 개별 SLA 달성률(0% 또는 100%)을 분리하여 모니터링합니다.
> * **배달 패널티 연동:** 배달 모드 활성화 시 라이더의 다중 분할 정차(가속 부하 2.4배) 및 도어 홀딩(대기 전력 1.8배) 물리 법칙이 적용됩니다.
""")

# ----------------- [2] SIDEBAR: 설정 변수 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=1, max_value=10)
    households_per_floor = st.number_input("층당 세대수 (가구)", value=4, min_value=1)
    stairs_floor = st.number_input("계단 이용 권장 층수", value=3, min_value=0, max_value=max_f)
    parking_usage_rate = st.number_input("🚗 주차장 이용 비율 (%)", value=30, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("🚀 물리 엔진 설정")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)
    
    fixed_door_moving_time = st.number_input("고정 기계 작동 시간 (초) [열림+닫힘]", value=4.0, min_value=1.0, step=0.5)
    base_door_time = st.number_input("기본 전체 문 시간 (초) [대기포함]", value=7.0, min_value=fixed_door_moving_time + 0.5, step=0.5)
    button_efficiency = st.number_input("🔘 닫힘 버튼 효율 (%)", value=40, min_value=0, max_value=100, step=5)
    
    pure_dwell_time = max(0.0, base_door_time - fixed_door_moving_time)
    saved_door_time = pure_dwell_time * (button_efficiency / 100)
    final_door_operating_time = base_door_time - saved_door_time

    st.divider()
    st.header("⚠️ 서비스 임계치 (SLA) 설정")
    lim_1f_up = st.number_input("SLA: 1층 → 거주층 (초)", value=45, min_value=10)
    lim_res_1f = st.number_input("SLA: 거주층 → 1층 (초)", value=55, min_value=10)
    lim_p_up = st.number_input("SLA: 주차장 → 거주층 (초)", value=50, min_value=10)
    lim_res_p = st.number_input("SLA: 거주층 → 주차장 (초)", value=65, min_value=10)

# ----------------- [3] MAIN: 인풋 설정 및 독립성 확보 -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f 
total_fs = len(FLOOR_LABELS)

st.header("⚙️ 시뮬레이션 타임라인 및 수동 배치 설정")
c_time, c_custom = st.columns([1, 1])

with c_time:
    st.write("##### ⏰ AI 최적화 및 한전 요금제 시간대 기준")
    time_options = [
        "새벽 시간 (00시~06시) [한전 경부하: 78원/kWh]", 
        "출근 시간 (07시~09시) [한전 최대부하: 195원/kWh]", 
        "낮 시간 (09시~18시) [한전 중부하: 132원/kWh]", 
        "퇴근 시간 (18시~20시) [한전 최대부하: 195원/kWh]", 
        "저녁 시간 (20시~23시) [한전 최대부하: 195원/kWh]"
    ]
    mode_selection = st.radio("시간대 패턴 선택", options=time_options, index=1, horizontal=False)
    mode_label = mode_selection.split(" (")[0]
    current_is_deliv = True if mode_label == "새벽 시간" else False
    
    if "경부하" in mode_selection:
        kepco_rate = 78.0
    elif "중부하" in mode_selection:
        kepco_rate = 132.0
    else:
        kepco_rate = 195.0

with c_custom:
    st.write("##### ✍️ 사용자 수동 배치 설정")
    m_cols = st.columns(num_elevators)
    manual_placements = []
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f, key=f"v_gran_matrix_{i}")
            manual_placements.append(val)

st.divider()

# --- 전략 배치 매핑 ---
strategies_config = {}
np.random.seed(42) 

strategies_config["전략 미적용 (랜덤 운행)"] = {"placements": list(np.random.randint(0, total_fs, num_elevators)), "logic": "자유 운행", "desc": "무작위 방치 상태"}

oe_placements = []
for i in range(num_elevators):
    if num_elevators == 1:
        oe_placements.append(int(np.random.randint(0, total_fs)))
    elif i % 2 == 0:
        odd_floors = [f for f in range(total_fs) if f <= idx_1f or (f - idx_1f) % 2 != 0]
        oe_placements.append(int(np.random.choice(odd_floors)))
    else:
        even_floors = [f for f in range(total_fs) if f <= idx_1f or (f - idx_1f) % 2 == 0]
        oe_placements.append(int(np.random.choice(even_floors)))
strategies_config["홀짝수층 분리 운행"] = {"placements": oe_placements, "logic": "홀짝 운행", "desc": "홀/짝수층 전담 정차로 감속 손실 방지"}

mid_idx = (total_fs + idx_1f) // 2
if num_elevators == 1:
    split_placements = [mid_idx]
else:
    split_placements = [int(idx_1f + (mid_idx-idx_1f)/2) if i < num_elevators/2 else int(mid_idx + (total_fs-mid_idx)/2) for i in range(num_elevators)]
strategies_config["고층부/저층부 분할배치"] = {"placements": split_placements, "logic": "분할 배치", "desc": "건물 상/하방 구역 분할 대기"}

strategies_config["베이스 스테이션 집중"] = {"placements": [idx_1f] * num_elevators, "logic": "자유 운행", "desc": "운행 종료 후 무조건 1층 로비 복귀"}

if num_elevators == 1:
    spacing_placements = [mid_idx]
else:
    spacing_placements = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config["동적 간격 배치"] = {"placements": spacing_placements, "logic": "자유 운행", "desc": "전체 가용 층수에 등간격 분산 대기"}

if mode_label == "새벽 시간":
    ai_pos = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2) if num_elevators > 1 else [idx_1f]
elif mode_label == "출근 시간":
    res_start = idx_1f + stairs_floor + 1
    res_end = total_fs - 1
    ai_pos = [int(res_start + (res_end - res_start) * (i + 1) / (num_elevators + 1)) if res_start < res_end else res_end for i in range(num_elevators)]
elif mode_label == "퇴근 시간":
    p_count = int(round(num_elevators * (parking_usage_rate / 100)))
    ai_pos = [0] * p_count + [idx_1f] * (num_elevators - p_count)
elif mode_label == "저녁 시간":
    lower_mid_f = int(idx_1f + (total_fs - idx_1f) * 0.3)
    ai_pos = []
    for i in range(num_elevators):
        if i % 2 == 0:
            ai_pos.append(idx_1f)
        else:
            ai_pos.append(lower_mid_f)
else:
    ai_pos = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config[f"AI 자동 최적화 ({mode_label})"] = {"placements": ai_pos, "logic": "자유 운행", "desc": "예상 수요 길목 지능형 유동 배치"}

strategies_config["사용자 수동 배치"] = {"placements": manual_placements, "logic": "자유 운행", "desc": "연구원 임의 정의 슬롯 배치"}

# ----------------- [4] 물리 엔진 코어 -----------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route_esg_sla(start, end, placements, logic, cong, is_deliv, eff, base_t, fixed_t, p_rate, s_floor, households):
    if abs(start - end) <= s_floor and start >= idx_1f:
        return 5.0, 0.001
    
    congestion_weights = {"매우 쾌적": 0.7, "쾌적": 0.9, "보통": 1.1, "혼잡": 1.8, "매우 혼잡": 2.5}
    h_weight = 1.0 + (households - 1) * 0.05
    w = congestion_weights[cong] * h_weight
    
    if is_deliv:
        w = w * 1.5
        delivery_stops_penalty = 2.4
        door_holding_penalty = 1.8
    else:
        delivery_stops_penalty = 1.0
        door_holding_penalty = 1.0
    
    avail = [i for i in range(num_elevators)]
    if num_elevators > 1:
        if "홀짝" in logic:
            avail = [i for i in avail if start <= idx_1f or (i % 2 == 0 and start % 2 != 0) or (i % 2 != 0 and start % 2 == 0)]
        elif "분할" in logic:
            mid = (total_fs + idx_1f) // 2
            avail = [i for i in avail if start <= idx_1f or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid)]
    if not avail: avail = [0]
    
    chosen_el_idx = avail[0]
    min_dist_m = abs(placements[chosen_el_idx] - start) * floor_height
    wait_t = get_phys_time(min_dist_m, max_velocity, acceleration)
    
    if logic == "베이스 스테이션 집중" and start != idx_1f:
        min_dist_m += (abs(end - idx_1f) * floor_height) 

    move_dist_m = abs(start - end) * floor_height
    move_t = get_phys_time(move_dist_m, max_velocity, acceleration)
    
    if start < idx_1f or end < idx_1f:
        wait_t = wait_t * (1 - (p_rate / 100) * 0.4)
    
    pure_dwell = max(0.0, base_t - fixed_t)
    door_eff_t = fixed_t + (pure_dwell * (1 - (eff/100)))
    if start == idx_1f: 
        door_eff_t = door_eff_t * 1.2
        
    final_time = (wait_t + move_t + (door_eff_t * w)) * (1.3 if is_deliv else 1.0)
    
    total_moving_dist = min_dist_m + move_dist_m
    moving_time_pure = get_phys_time(total_moving_dist, max_velocity, acceleration)
    
    energy_move = ((500 * 9.8 * max_velocity * moving_time_pure) / (0.85 * 3600 * 1000)) * delivery_stops_penalty
    energy_door = 0.001 * w * door_holding_penalty
    total_kwh = energy_move + energy_door
    
    return final_time, total_kwh

# ----------------- [5] 통합 가동 및 동선별 매트릭스 도출 -----------------
st.subheader("🌐 시뮬레이션 환경 조건 가동")
c_env1, c_env2 = st.columns(2)
with c_env1: 
    congestion = st.radio("건물 내부 혼잡도 세부 선택", options=["매우 쾌적", "쾌적", "보통", "혼잡", "매우 혼잡"], index=2, horizontal=True)
with c_env2: 
    delivery_mode = st.toggle("📦 배달 패널티 활성화", value=current_is_deliv)

if st.button("🚀 동선별 SLA 정밀 시뮬레이션 가동", type="primary", use_container_width=True):
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
                p_rate_param, s_floor_param, households_per_floor
            )
            
            sla_diff = calc_time - target_sla
            is_sla_pass = 100.0 if sla_diff <= 0 else 0.0 # 개별 동선은 패스(100%) 아니면 실패(0%)
            sla_excess = max(0.0, sla_diff) 
            
            calc_cost = calc_kwh * kepco_rate
            
            matrix_results.append({
                "운영 전략": strat_name,
                "동선 시나리오": s_name,
                "실제 소요시간": calc_time,
                "목표 SLA": target_sla,
                "SLA 초과(초)": sla_excess,
                "SLA 달성률": is_sla_pass,
                "전기 요금(원)": calc_cost
            })
            
    df_matrix = pd.DataFrame(matrix_results)
    
    # 📈 동선별 정밀 데이터 가독성 정제
    st.write("### 📈 [동선별 정밀 스코어보드] 운영 전략 × 시나리오 매트릭스")
    
    # 사용자가 보기 편하게 테이블 재구성 (Pivot 형태)
    final_rows = []
    for strat_name in strategies_config.keys():
        strat_df = df_matrix[df_matrix["운영 전략"] == strat_name]
        
        row_data = {"운영 전략": strat_name}
        
        # 4개 동선을 돌며 시간과 %를 한 셀에 합쳐서 표기하거나 분리
        for _, row in strat_df.iterrows():
            scen = row["동선 시나리오"]
            time_v = row["실제 소요시간"]
            pass_v = row["SLA 달성률"]
            excess_v = row["SLA 초과(초)"]
            
            # 셀 안에 가독성 좋게 텍스트 포맷팅
            status_icon = "⭕" if pass_v == 100.0 else f"❌ (+{excess_v:.1f}초)"
            row_data[f"{scen} (소요시간)"] = f"{time_v:.1f}초"
            row_data[f"{scen} (달성률)"] = f"{pass_v:.0f}% ({status_icon})"
            
        final_rows.append(row_data)
        
    df_pivot = pd.DataFrame(final_rows).set_index("운영 전략")
    
    # 동선별 컬럼 순서 정렬
    ordered_cols = [
        "1층 ⬆️ 거주층 (소요시간)", "1층 ⬆️ 거주층 (달성률)",
        "거주층 ⬇️ 1층 (소요시간)", "거주층 ⬇️ 1층 (달성률)",
        "주차장 ⬆️ 거주층 (소요시간)", "주차장 ⬆️ 거주층 (달성률)",
        "거주층 ⬇️ 주차장 (소요시간)", "거주층 ⬇️ 주차장 (달성률)"
    ]
    st.dataframe(df_pivot[ordered_cols], use_container_width=True)
    
    # 📊 시각화 보조 차트 (동선별 SLA 초과 현황)
    st.write("### 📊 동선별 실시간 데드라인 초과 폭 비교")
    sla_chart = alt.Chart(df_matrix).mark_bar().encode(
        x=alt.X('동선 시나리오:N', axis=alt.Axis(title="시나리오 노선")),
        y=alt.Y('실제 소요시간:Q', title='소요 시간 (초)'),
        color='운영 전략:N',
        column='운영 전략:N'
    ).properties(width=150, height=220)
    st.altair_chart(sla_chart)
    
    st.info("💡 **결과 해석 팁:** 특정 동선에서 `0% (❌ +11.7초)` 형태로 표시되는 것은 해당 동선의 목표 SLA 기준치를 넘겼다는 뜻입니다. 왜 홀짝수층 배치가 전체 평균 지연 속에서도 25%를 방어했는지 그 정답이 위 표에 명확하게 분리되어 나타납니다.")
