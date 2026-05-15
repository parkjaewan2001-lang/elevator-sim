import streamlit as st
import pandas as pd
import numpy as np

# ----------------- [1] UI 설정 -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")
st.caption("그래프 시인성 개선 및 개선율(%) 분석 기능이 추가된 최종 정밀 버전입니다.")

# ----------------- [2] SIDEBAR: 설정 변수 -----------------
with st.sidebar:
    st.header("🏗️ 건물 및 세대 설정")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("지상 최고층", value=30, step=1)
    with c2: min_f = st.number_input("지하 최저층", value=5, step=1)
    
    households_per_floor = st.number_input("층당 세대수", value=4, min_value=1)
    stairs_floor = st.slider("계단 이용 층수", 1, 5, 3)
    num_elevators = st.number_input("엘리베이터 개수", value=2, min_value=2, max_value=10)

    st.divider()
    st.header("🚀 물리 엔진 및 문 개폐")
    floor_height = st.number_input("층간 높이 (m)", value=3.0)
    max_velocity = st.number_input("정격 속도 (m/s)", value=2.5)
    acceleration = st.number_input("가속도 (m/s²)", value=1.0)
    
    # 기본 문 시간 정의 및 설명
    base_door_time = st.number_input("기본 문 시간 (초)", value=7.0, 
                                    help="센서 감지가 없을 때 문이 열려 있다가 자동으로 닫힐 때까지의 표준 시간입니다.")
    button_efficiency = st.slider("🔘 닫힘 버튼 효율 (%)", 0, 100, 40)
    
    # 닫힘 버튼 클릭 시 실제 시간 계산
    actual_close_t = base_door_time * (1 - (button_efficiency / 100))
    st.info(f"✨ **문 닫힘 분석:** 버튼 클릭 시 **{actual_close_t:.1f}초** 만에 닫힘 (표준 대비 {button_efficiency}% 단축)")

    st.divider()
    st.header("⚠️ 서비스 임계치 (SLA)")
    lim_1f_up = st.slider("1층 → 거주층", 30, 180, 60)
    lim_res_1f = st.slider("거주층 → 1층", 30, 180, 80)
    lim_p_up = st.slider("주차장 → 거주층", 30, 180, 70)
    lim_res_p = st.slider("거주층 → 주차장", 30, 180, 90)

# ----------------- [3] MAIN: 전략 설정 -----------------
st.header("⚙️ 분석 전략 설정")

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

# 변수 초기화 (안정성 확보)
logic_type = "전 층 자유 운행 (기본)"
placement_option = "사용 안 함"
mode_label = "균등 분포"
final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
current_is_deliv = False 

col_strat1, col_strat2 = st.columns(2)

with col_strat1:
    st.subheader("🕹️ 운영 알고리즘")
    logic_option = st.selectbox(
        "운행 규칙 선택",
        ["사용 안 함 (전 층 자유 운행)", "홀짝수층 분리 운행", "저층/고층부 분할 운행"]
    )
    logic_type = "전 층 자유 운행 (기본)" if "사용 안 함" in logic_option else logic_option

    # 분할 운행 가이드
    if "저층/고층부" in logic_option:
        mid = total_fs // 2
        st.warning(f"💡 **최적 배치 가이드:** 저층({FLOOR_LABELS[idx_1f + (mid-idx_1f)//2]}), 고층({FLOOR_LABELS[mid + (total_fs-mid)//2]}) 배치를 권장합니다.")

with col_strat2:
    st.subheader("📍 대기 위치 배치")
    placement_option = st.selectbox("배치 방식 선택", ["사용 안 함", "AI 자동 최적화 배치", "사용자 수동 배치"])

st.divider()

# 배치 전략 UI 제어
if placement_option != "사용 안 함":
    if placement_option == "AI 자동 최적화 배치":
        mode_label = st.select_slider("⏰ 시간대 패턴", options=["새벽 시간", "출근 시간", "낮 시간", "퇴근 시간"], value="낮 시간")
        if mode_label == "새벽 시간":
            final_placements = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2)
            current_is_deliv = True 
        elif mode_label == "출근 시간":
            final_placements = [int(np.percentile(range(idx_1f+stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
        elif mode_label == "퇴근 시간":
            final_placements = [idx_1f] * num_elevators
        else: final_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
            
    elif placement_option == "사용자 수동 배치":
        mode_label = "수동 지정"
        m_cols = st.columns(num_elevators)
        final_placements = []
        for i in range(num_elevators):
            with m_cols[i]:
                val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f)
                final_placements.append(val)

    st.write(f"**현재 설정된 배치 상태 ({mode_label}):**")
    disp_cols = st.columns(num_elevators)
    for i, p in enumerate(final_placements):
        disp_cols[i].metric(f"EL {chr(65+i)}", FLOOR_LABELS[p])
    st.divider()

# ----------------- [4] 시뮬레이션 엔진 -----------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route(start, end, placements, logic, cong, is_deliv, eff, base_t):
    w = {"매우 쾌적": 0.7, "보통": 1.1, "매우 혼잡": 2.5}[cong]
    actual_f = start - min_f
    avail = []
    for i in range(num_elevators):
        if "자유 운행" in logic: avail.append(i)
        elif "홀짝" in logic:
            if start == idx_1f or (i%2 == 0 and actual_f%2 != 0) or (i%2 != 0 and actual_f%2 == 0): avail.append(i)
        elif "분할" in logic:
            mid = total_fs // 2
            if start == idx_1f or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid): avail.append(i)
    if not avail: avail = list(range(num_elevators))
    
    min_dist_m = min([abs(placements[i] - start) for i in avail]) * floor_height
    wait_t = get_phys_time(min_dist_m, max_velocity, acceleration)
    move_t = get_phys_time(abs(start - end) * floor_height, max_velocity, acceleration)
    door_t = base_t * (1 - (eff/100)) if start > idx_1f else base_t * 1.2
    loading_t = (door_t * w) * (1 + (households_per_floor * 0.05))
    total_t = wait_t + move_t + loading_t
    if is_deliv: total_t *= 1.3
    return total_t

# ----------------- [5] 실행 및 개선 분석 -----------------
st.subheader("🌐 환경 정보")
c_env1, c_env2 = st.columns(2)
with c_env1: congestion = st.select_slider("건물 혼잡도", options=["매우 쾌적", "보통", "매우 혼잡"], value="보통")
with c_env2: delivery_mode = st.toggle("📦 배송 지연 강제 활성화", value=current_is_deliv)

if st.button("🚀 통합 비교 분석 실행", type="primary", use_container_width=True):
    default_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    avg_f = idx_1f + (max_f * 0.7)
    scenarios = {"1층 ⬆️ 거주층": (idx_1f, avg_f, lim_1f_up), "거주층 ⬇️ 1층": (avg_f, idx_1f, lim_res_1f),
                 "주차장 ⬆️ 거주층": (0, avg_f, lim_p_up), "거주층 ⬇️ 주차장": (avg_f, 0, lim_res_p)}

    st.subheader("📊 전략 전/후 비교 리포트")
    m_cols = st.columns(4)
    chart_data = []

    for i, (name, (s, e, l)) in enumerate(scenarios.items()):
        # 1. 전략 미적용
        base_t = simulate_route(s, e, default_placements, "자유 운행", "보통", False, 0, base_door_time)
        # 2. 전략 적용
        strat_t = simulate_route(s, e, final_placements, logic_type, congestion, delivery_mode, button_efficiency, base_door_time)
        
        diff = base_t - strat_t
        with m_cols[i]:
            st.metric(name, f"{strat_t:.1f}s", delta=f"{diff:+.1f}s")
            if strat_t > l: st.error(f"SLA 미달 (목표 {l}s)")
            else: st.success(f"SLA 준수 (목표 {l}s)")
        
        chart_data.append({"노선": name, "전략 미적용": base_t, "전략 적용": strat_t})

    st.divider()
    
    # 그래프 및 상세 데이터 가공
    df_res = pd.DataFrame(chart_data)
    df_res['개선량(sec)'] = df_res['전략 미적용'] - df_res['전략 적용']
    # 개선율 계산 (0으로 나누기 방지)
    df_res['개선량(%)'] = (df_res['개선량(sec)'] / df_res['전략 미적용'] * 100).fillna(0)

    col_viz1, col_viz2 = st.columns([1, 1])
    
    with col_viz1:
        st.write("#### 📈 노선별 시간 비교 (Grouped Bar)")
        # 막대그래프 형태로 보기 편하게 구조 변경
        chart_melted = df_res.melt(id_vars='노선', value_vars=['전략 미적용', '전략 적용'], var_name='구분', value_name='시간(초)')
        st.bar_chart(chart_melted, x='노선', y='시간(초)', color='구분', use_container_width=True)

    with col_viz2:
        st.write("#### 📝 상세 분석 데이터")
        # 개선량(%)을 포함한 테이블 출력
        st.dataframe(
            df_res.set_index("노선").style.format({
                "전략 미적용": "{:.2f}",
                "전략 적용": "{:.2f}",
                "개선량(sec)": "{:+.2f}",
                "개선량(%)": "{:+.1f}%"
            }),
            use_container_width=True
        )
