import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] UI 설정 -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")
st.subheader("📊 전(全) 전략 다중 비교 매트릭스 시스템")

# ----------------- [2] SIDEBAR: 설정 변수 (숫자 입력 방식으로 통일) -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=2, max_value=10)
    households_per_floor = st.number_input("층당 세대수 (가구)", value=4, min_value=1)
    stairs_floor = st.number_input("계단 이용 권장 층수", value=3, min_value=0, max_value=max_f)
    
    # [변경] 주차장 이용 비율: 직접 숫자로 입력 가능하도록 number_input으로 교체
    parking_usage_rate = st.number_input("🚗 주차장 이용 비율 (%)", value=30, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("🚀 물리 엔진 설정")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)
    
    base_door_time = st.number_input("기본 문 시간 (초)", value=7.0)
    button_efficiency = st.slider("🔘 닫힘 버튼 효율 (%)", 0, 100, 40)

    st.divider()
    st.header("⚠️ 서비스 임계치 (SLA)")
    lim_1f_up = st.slider("1층 → 거주층", 30, 180, 60)
    lim_res_1f = st.slider("거주층 → 1층", 30, 180, 80)
    lim_p_up = st.slider("주차장 → 거주층", 30, 180, 70)
    lim_res_p = st.slider("거주층 → 주차장", 30, 180, 90)

# ----------------- [3] MAIN: 전략별 배치 사전 연산 -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f 
total_fs = len(FLOOR_LABELS)

st.header("⚙️ 시뮬레이션 타임라인 및 수동 배치 설정")
c_time, c_custom = st.columns([1, 1])

with c_time:
    st.write("##### ⏰ AI 최적화 시간대 기준")
    mode_label = st.select_slider("시간대 패턴 선택", options=["새벽 시간", "출근 시간", "낮 시간", "퇴근 시간"], value="출근 시간")
    
    current_is_deliv = True if mode_label == "새벽 시간" else False

with c_custom:
    st.write("##### ✍️ 사용자 수동 배치 실시간 설정")
    m_cols = st.columns(num_elevators)
    manual_placements = []
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f, key=f"v_matrix_{i}")
            manual_placements.append(val)

st.divider()

# --- 각 전략별 엘리베이터 배치 위치 계산 ---
strategies_config = {}

# 1. 전략 미적용 (모두 1층 대기)
strategies_config["전략 미적용 (1층 고정)"] = {"placements": [idx_1f] * num_elevators, "logic": "자유 운행"}

# 2. 홀짝수층 분리 운행
strategies_config["홀짝수층 분리 운행"] = {"placements": [idx_1f] * num_elevators, "logic": "홀짝 운행"}

# 3. 고층부/저층부 분할 배치
mid_idx = (total_fs + idx_1f) // 2
strategies_config["고층부/저층부 분할배치"] = {
    "placements": [int(idx_1f + (mid_idx-idx_1f)/2) if i < num_elevators/2 else int(mid_idx + (total_fs-mid_idx)/2) for i in range(num_elevators)],
    "logic": "분할 배치"
}

# 4. AI 자동 최적화 배치
if mode_label == "새벽 시간":
    ai_pos = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2)
elif mode_label == "출근 시간":
    res_start = idx_1f + stairs_floor + 1
    res_end = total_fs - 1
    ai_pos = [int(res_start + (res_end - res_start) * (i + 1) / (num_elevators + 1)) if res_start < res_end else res_end for i in range(num_elevators)]
elif mode_label == "퇴근 시간":
    p_count = int(round(num_elevators * (parking_usage_rate / 100)))
    ai_pos = [0] * p_count + [idx_1f] * (num_elevators - p_count)
else:
    ai_pos = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config[f"AI 자동 최적화 ({mode_label})"] = {"placements": ai_pos, "logic": "자유 운행"}

# 5. 사용자 수동 배치
strategies_config["사용자 수동 배치"] = {"placements": manual_placements, "logic": "자유 운행"}


# --- 배치 현황 그리드 대시보드 표시 ---
st.write("### 📍 각 전략별 엘리베이터 실시간 배치 지도")
st.info("※ 홀짝수층 분리 운행은 기본 위치(1층)에서 대기하되 탑승 제한 규칙이 적용됩니다.")
grid_cols = st.columns(len(strategies_config))

for idx, (s_name, config) in enumerate(strategies_config.items()):
    with grid_cols[idx]:
        st.markdown(f"**{s_name}**")
        for i, pos in enumerate(config["placements"]):
            st.caption(f"EL {chr(65+i)} : `{FLOOR_LABELS[pos]}`")

st.divider()

# ----------------- [4] 시뮬레이션 매트릭스 엔진 -----------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route(start, end, placements, logic, cong, is_deliv, eff, base_t, p_rate, s_floor, households):
    if abs(start - end) <= s_floor and start >= idx_1f:
        return 5.0

    h_weight = 1.0 + (households - 1) * 0.05
    w = {"매우 쾌적": 0.7, "보통": 1.1, "매우 혼잡": 2.5}[cong] * h_weight
    
    avail = [i for i in range(num_elevators)]
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
    door_eff_t = base_t * (1 - (eff/100)) if start > idx_1f else base_t * 1.2
    
    return (wait_t + move_t + (door_eff_t * w)) * (1.3 if is_deliv else 1.0)

# ----------------- [5] 동시 실행 및 통합 시각화 -----------------
st.subheader("🌐 시뮬레이션 매트릭스 가동")
c_env1, c_env2 = st.columns(2)
with c_env1: congestion = st.select_slider("건물 내부 혼잡도", options=["매우 쾌적", "보통", "매우 혼잡"], value="보통")
with c_env2: delivery_mode = st.toggle("📦 배송 지연 패널티 반영", value=current_is_deliv)

if st.button("🚀 모든 운영 전략 동시 분석 시작", type="primary", use_container_width=True):
    avg_res_f = int(idx_1f + (max_f - 1) * 0.7)
    scenarios = {
        "1층 ⬆️ 거주층": (idx_1f, avg_res_f, lim_1f_up),
        "거주층 ⬇️ 1층": (avg_res_f, idx_1f, lim_res_1f),
        "주차장 ⬆️ 거주층": (0, avg_res_f, lim_p_up),
        "거주층 ⬇️ 주차장": (avg_res_f, 0, lim_res_p)
    }
    
    matrix_results = []
    
    # 모든 시나리오 x 모든 전략 동시 연산 루프
    for s_name, (start, end, limit) in scenarios.items():
        for strat_name, config in strategies_config.items():
            # 전략 미적용 상태일 때는 문 효율(닫힘버튼 효율)이나 주차장 보정을 적용하지 않음
            eff_param = button_efficiency if strat_name != "전략 미적용 (1층 고정)" else 0
            p_rate_param = parking_usage_rate if strat_name != "전략 미적용 (1층 고정)" else 0
            s_floor_param = stairs_floor if strat_name != "전략 미적용 (1층 고정)" else 0
            
            calc_time = simulate_route(
                start, end, config["placements"], config["logic"], 
                congestion, delivery_mode, eff_param, base_door_time, 
                p_rate_param, s_floor_param, households_per_floor
            )
            
            matrix_results.append({
                "시나리오 노선": s_name,
                "운영 전략": strat_name,
                "소요 시간(초)": round(calc_time, 1),
                "SLA 임계치": limit,
                "SLA 달성여부": "통과" if calc_time <= limit else "미달"
            })
            
    df_matrix = pd.DataFrame(matrix_results)
    
    # 1. 멀티 라인 차트 시각화
    st.write("### 📈 전략 통합 비교 데이터 차트")
    multi_line = alt.Chart(df_matrix).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X('시나리오 노선:N', title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y('소요 시간(초):Q', title='시간 (초)'),
        color=alt.Color('운영 전략:N', scale=alt.Scale(scheme='category10')),
        tooltip=['시나리오 노선', '운영 전략', '소요 시간(초)', 'SLA 달성여부']
    ).properties(width=1000, height=500).interactive()
    
    st.altair_chart(multi_line, use_container_width=True)
    
    # 2. 피벗 데이터 테이블을 활용한 직관적인 비교 교차표
    st.write("### 📊 전략 효율성 대조 Matrix 테이블")
    
    df_pivot = df_matrix.pivot(index='시나리오 노선', columns='운영 전략', values='소요 시간(초)').reset_index()
    
    # 대조군인 '전략 미적용' 대비 개선 시간 계산용 기본 테이블 생성
    base_col = "전략 미적용 (1층 고정)"
    
    st.dataframe(df_pivot.set_index('시나리오 노선'), use_container_width=True)
    
    # 3. 종합 요약 알림창
    st.write("### 💡 종합 데이터 인사이트 요약")
    summary_data = df_matrix.groupby('운영 전략')['소요 시간(초)'].mean().reset_index()
    best_strategy = summary_data.sort_values(by='소요 시간(초)').iloc[0]['운영 전략']
    best_time = summary_data.sort_values(by='소요 시간(초)').iloc[0]['소요 시간(초)']
    
    st.success(f"🏆 종합 분석 결과, 현재 조건에서 가장 평균 대기 시간이 짧은 최적의 운영 전략은 **[{best_strategy}]** (평균 {best_time:.1f}초) 입니다.")
