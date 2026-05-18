import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] UI 설정 -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")
st.subheader("📊 전(全) 전략 다중 비교 및 효율성 분석 매트릭스")

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
    
    st.info(f"""
    ⚙️ **도어 메커니즘 실시간 프로파일링:**
    * 하드웨어 한계 구동 시간: **{fixed_door_moving_time:.1f}초**
    * 디폴트 승객 개방 대기 시간: **{pure_dwell_time:.1f}초**
    * 닫힘 버튼 클릭 단축 이득: **-{saved_door_time:.2f}초**
    * **최종 플랫폼 정지 시간: {final_door_operating_time:.2f}초**
    """)

    st.divider()
    st.header("⚠️ 서비스 임계치 (SLA) 설정")
    lim_1f_up = st.number_input("SLA: 1층 → 거주층 (초)", value=60, min_value=10)
    lim_res_1f = st.number_input("SLA: 거주층 → 1층 (초)", value=80, min_value=10)
    lim_p_up = st.number_input("SLA: 주차장 → 거주층 (초)", value=70, min_value=10)
    lim_res_p = st.number_input("SLA: 거주층 → 주차장 (초)", value=90, min_value=10)

# ----------------- [3] MAIN: 인풋 설정 및 독립성 확보 -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f 
total_fs = len(FLOOR_LABELS)

st.header("⚙️ 시뮬레이션 타임라인 및 수동 배치 설정")
c_time, c_custom = st.columns([1, 1])

with c_time:
    st.write("##### ⏰ AI 최적화 시간대 기준")
    time_options = [
        "새벽 시간 (00시~06시)", 
        "출근 시간 (07시~09시)", 
        "낮 시간 (09시~18시)", 
        "퇴근 시간 (18시~20시)", 
        "저녁 시간 (20시~23시)"
    ]
    mode_selection = st.radio("시간대 패턴 선택", options=time_options, index=1, horizontal=True)
    
    mode_label = mode_selection.split(" (")[0]
    current_is_deliv = True if mode_label == "새벽 시간" else False

with c_custom:
    st.write("##### ✍️ 사용자 수동 배치 설정 (AI 자동 최적화와 상호 배타적)")
    m_cols = st.columns(num_elevators)
    manual_placements = []
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f, key=f"v_matrix_v17_{i}")
            manual_placements.append(val)

st.divider()

# --- 각 전략별 독립 배치 계산 및 매커니즘 설명 정의 ---
strategies_config = {}
np.random.seed(42) 

# 1. 전략 미적용
strategies_config["전략 미적용 (랜덤 운행)"] = {
    "placements": list(np.random.randint(0, total_fs, num_elevators)), 
    "logic": "자유 운행",
    "desc": "알고리즘 없이 이전 운행이 끝난 층에 무작위로 방치되는 상태입니다. 비교 기준점(Baseline) 역할을 합니다."
}

# 2. 홀짝수층 분리 운행
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
strategies_config["홀짝수층 분리 운행"] = {
    "placements": oe_placements, 
    "logic": "홀짝 운행",
    "desc": "엘리베이터별로 홀수층과 짝수층을 전담하여 정차 횟수를 절반으로 줄이고 동력 효율을 높이는 전통적 방식입니다."
}

# 3. 고층부/저층부 분할 배치
mid_idx = (total_fs + idx_1f) // 2
if num_elevators == 1:
    split_placements = [mid_idx]
else:
    split_placements = [int(idx_1f + (mid_idx-idx_1f)/2) if i < num_elevators/2 else int(mid_idx + (total_fs-mid_idx)/2) for i in range(num_elevators)]
strategies_config["고층부/저층부 분할배치"] = {
    "placements": split_placements, 
    "logic": "분할 배치",
    "desc": "건물 수직 반경을 하부와 상부 구역으로 쪼개어 대기합니다. 장거리 이동 병목 현상을 방어하기에 유리합니다."
}

# 4. 베이스 스테이션 집중
strategies_config["베이스 스테이션 집중"] = {
    "placements": [idx_1f] * num_elevators, 
    "logic": "자유 운행",
    "desc": "운행이 끝나면 무조건 메인 로비(1층)로 강제 복귀합니다. 외부 입주민 유입이 압도적인 패턴에 특화되어 있습니다."
}

# 5. 동적 간격 배치
if num_elevators == 1:
    spacing_placements = [mid_idx]
else:
    spacing_placements = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config["동적 간격 배치"] = {
    "placements": spacing_placements, 
    "logic": "자유 운행",
    "desc": "차량 간 뭉침 현상(Bunching)을 예방하기 위해 전체 가용 층수를 대수대로 등간격 분산시켜 촘촘히 대기합니다."
}

# 6. AI 자동 최적화 배치
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

strategies_config[f"AI 자동 최적화 ({mode_label})"] = {
    "placements": ai_pos, 
    "logic": "자유 운행",
    "desc": f"선택된 '{mode_label}' 유동인구 통계를 분석하여, 상/하행 실시간 예상 컴포넌트 길목에 유동 배정하는 지능형 로직입니다."
}

# 7. 사용자 수동 배치
strategies_config["사용자 수동 배치"] = {
    "placements": manual_placements, 
    "logic": "자유 운행",
    "desc": "상단 슬롯에서 연구원(사용자)이 임의로 정의한 고정 층수에 수동 스탠바이시키는 직관적 제어 모드입니다."
}


# --- [수정] 배치 현황 및 로직 설명 그리드 표시 ---
st.write("### 📍 각 운영 전략별 엘리베이터 시뮬레이션 초기 위치 지도 및 로직 가이드")
grid_cols = st.columns(len(strategies_config))
for idx, (s_name, config) in enumerate(strategies_config.items()):
    with grid_cols[idx]:
        st.markdown(f"**{s_name}**")
        
        # 층수 가시화 바인딩
        if s_name == "전략 미적용 (랜덤 운행)":
            st.info("🔄 전 층 자유 랜덤 분산 운행")
        elif s_name == "홀짝수층 분리 운행" and num_elevators > 1:
            st.info("⚡ 전담 구역 내 가변 대기")
            for i in range(num_elevators):
                st.caption(f"EL {chr(65+i)} : `{'홀수' if i % 2 == 0 else '짝수'}층 전담`")
        else:
            for i, pos in enumerate(config["placements"]):
                st.caption(f"EL {chr(65+i)} : `{FLOOR_LABELS[pos]}`")
                
        # [추가] 각 로직의 원리와 의미를 명확히 이해할 수 있도록 주석창 추가
        st.caption(f"💡 {config['desc']}")

st.divider()

# ----------------- [4] 시뮬레이션 엔진 -----------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route(start, end, placements, logic, cong, is_deliv, eff, base_t, fixed_t, p_rate, s_floor, households):
    if abs(start - end) <= s_floor and start >= idx_1f:
        return 5.0

    congestion_weights = {
        "매우 쾌적": 0.7, 
        "쾌적": 0.9, 
        "보통": 1.1, 
        "혼잡": 1.8, 
        "매우 혼잡": 2.5
    }
    h_weight = 1.0 + (households - 1) * 0.05
    w = congestion_weights[cong] * h_weight
    
    avail = [i for i in range(num_elevators)]
    
    if num_elevators > 1:
        if "홀짝" in logic:
            avail = [i for i in avail if start <= idx_1f or (i % 2 == 0 and start % 2 != 0) or (i % 2 != 0 and start % 2 == 0)]
        elif "분할" in logic:
            mid = (total_fs + idx_1f) // 2
            avail = [i for i in avail if start <= idx_1f or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid)]
    
    if not avail: avail = [0]
    
    min_dist_m = min([abs(placements[idx] - start) for idx in avail]) * floor_height
    wait_t = get_phys_time(min_dist_m, max_velocity, acceleration)
    
    if start < idx_1f or end < idx_1f:
        wait_t = wait_t * (1 - (p_rate / 100) * 0.4)
    
    move_t = get_phys_time(abs(start - end) * floor_height, max_velocity, acceleration)
    
    pure_dwell = max(0.0, base_t - fixed_t)
    door_eff_t = fixed_t + (pure_dwell * (1 - (eff/100)))
    
    if start == idx_1f: 
        door_eff_t = door_eff_t * 1.2
    
    return (wait_t + move_t + (door_eff_t * w)) * (1.3 if is_deliv else 1.0)

# ----------------- [5] 통합 실행 및 대조 분석 -----------------
st.subheader("🌐 멀티 매트릭스 시뮬레이션 가동")
c_env1, c_env2 = st.columns(2)

with c_env1: 
    congestion = st.radio(
        "건물 내부 혼잡도 세부 선택", 
        options=["매우 쾌적", "쾌적", "보통", "혼잡", "매우 혼잡"], 
        index=2, 
        horizontal=True
    )
    
with c_env2: 
    delivery_mode = st.toggle("📦 배송 지연 패널티 반영", value=current_is_deliv)

if st.button("🚀 전체 분석 및 개선 지표 산출 시작", type="primary", use_container_width=True):
    avg_res_f = int(idx_1f + (max_f - 1) * 0.7)
    scenarios = {
        "1층 ⬆️ 거주층": (idx_1f, avg_res_f, lim_1f_up),
        "거주층 ⬇️ 1층": (avg_res_f, idx_1f, lim_res_1f),
        "주차장 ⬆️ 거주층": (0, avg_res_f, lim_p_up),
        "거주층 ⬇️ 주차장": (avg_res_f, 0, lim_res_p)
    }
    
    matrix_results = []
    
    for s_name, (start, end, limit) in scenarios.items():
        for strat_name, config in strategies_config.items():
            eff_param = button_efficiency if strat_name != "전략 미적용 (랜덤 운행)" else 0
            p_rate_param = parking_usage_rate if strat_name != "전략 미적용 (랜덤 운행)" else 0
            s_floor_param = stairs_floor if strat_name != "전략 미적용 (랜덤 운행)" else 0
            
            calc_time = simulate_route(
                start, end, config["placements"], config["logic"], 
                congestion, delivery_mode, eff_param, base_door_time, fixed_door_moving_time,
                p_rate_param, s_floor_param, households_per_floor
            )
            
            matrix_results.append({
                "시나리오 노선": s_name,
                "운영 전략": strat_name,
                "소요 시간(초)": round(calc_time, 1),
                "SLA 임계치": limit
            })
            
    df_matrix = pd.DataFrame(matrix_results)
    
    # 1. 멀티 라인 차트 시각화
    st.write("### 📈 전략별 성능 추이 시각화 (기준: 전략 미적용 랜덤 운행)")
    multi_line = alt.Chart(df_matrix).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X('시나리오 노선:N', title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y('소요 시간(초):Q', title='시간 (초)'),
        color=alt.Color('운영 전략:N', scale=alt.Scale(scheme='category10')),
        tooltip=['시나리오 노선', '운영 전략', '소요 시간(초)']
    ).properties(width=1000, height=450).interactive()
    st.altair_chart(multi_line, use_container_width=True)
    
    # 2. 피벗 후 변동 수치 계산 처리
    st.write("### 📊 전략 효율성 대조 및 시간 단축 변동 매트릭스")
    df_pivot = df_matrix.pivot(index='시나리오 노선', columns='운영 전략', values='소요 시간(초)').reset_index()
    
    base_col = "전략 미적용 (랜덤 운행)"
    final_table_data = {"시나리오 노선": df_pivot["시나리오 노선"]}
    final_table_data[f"{base_col} (기준값)"] = df_pivot[base_col].map(lambda x: f"{x:.1f}s")
    
    for col in df_pivot.columns:
        if col in ["시나리오 노선", base_col]:
            continue
        
        diff_sec = df_pivot[col] - df_pivot[base_col]
        diff_pct = (diff_sec / df_pivot[base_col]) * 100
        
        final_table_data[col] = df_pivot[col].astype(str) + "s"
        final_table_data[f"{col} 변동량 (초)"] = diff_sec.map(lambda x: f"{x:+.1f}초")
        final_table_data[f"{col} 효율 (%)"] = diff_pct.map(lambda x: f"{x:+.1f}%")
        
    df_final_render = pd.DataFrame(final_table_data).set_index("시나리오 노선")
    
    ordered_cols = [f"{base_col} (기준값)"]
    for col in df_pivot.columns:
        if col not in ["시나리오 노선", base_col]:
            ordered_cols.extend([col, f"{col} 변동량 (초)", f"{col} 효율 (%)"])
            
    st.dataframe(df_final_render[ordered_cols], use_container_width=True)
