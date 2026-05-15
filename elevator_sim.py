import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] UI 설정 -----------------
st.set_page_config(page_title="Elevator Experiment Lab", layout="wide")
st.title("🏢 Elevator Strategic Experiment Lab")

# ----------------- [2] SIDEBAR: 설정 변수 (물리 엔진 & SLA) -----------------
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
    
    base_door_time = st.number_input("기본 문 시간 (초)", value=7.0)
    button_efficiency = st.slider("🔘 닫힘 버튼 효율 (%)", 0, 100, 40)
    st.info(f"✨ **문 닫힘 분석:** 버튼 클릭 시 시간 **{button_efficiency}%** 감소 적용")

    st.divider()
    st.header("⚠️ 서비스 임계치 (SLA)")
    lim_1f_up = st.slider("1층 → 거주층", 30, 180, 60)
    lim_res_1f = st.slider("거주층 → 1층", 30, 180, 80)
    lim_p_up = st.slider("주차장 → 거주층", 30, 180, 70)
    lim_res_p = st.slider("거주층 → 주차장", 30, 180, 90)

# ----------------- [3] MAIN: 전략 및 운영 설정 -----------------
st.header("⚙️ 분석 전략 및 운영 설정")

FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f
total_fs = len(FLOOR_LABELS)

col_strat1, col_strat2 = st.columns(2)
with col_strat1:
    logic_option = st.selectbox("운행 규칙 선택", ["사용 안 함 (전 층 자유 운행)", "홀짝수층 분리 운행", "고층부/저층부 분할 배치"])
    logic_type = "전 층 자유 운행 (기본)" if "사용 안 함" in logic_option else logic_option

with col_strat2:
    placement_option = st.selectbox("배치 방식 선택", ["사용 안 함", "AI 자동 최적화 배치", "사용자 수동 배치"])

st.divider()

active_placements = []
current_is_deliv = False

# [기능 통합] 운행 규칙이나 배치 방식 중 하나라도 활성화되면 시간대 패턴 설정 가능
if logic_option != "사용 안 함 (전 층 자유 운행)" or placement_option == "AI 자동 최적화 배치":
    st.subheader("⏰ 운영 및 배치 시간대 설정")
    mode_label = st.select_slider("시뮬레이션 시간대 패턴 선택", options=["새벽 시간", "출근 시간", "낮 시간", "퇴근 시간"], value="낮 시간")
    
    # 시간대별 배치 로직 계산
    if mode_label == "새벽 시간":
        active_placements = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2)
        current_is_deliv = True 
    elif mode_label == "출근 시간":
        active_placements = [int(np.percentile(range(idx_1f + stairs_floor, total_fs), (100/(num_elevators+1))*(i+1))) for i in range(num_elevators)]
    elif mode_label == "퇴근 시간":
        active_placements = [idx_1f] * num_elevators
    else: # 낮 시간
        active_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]

if placement_option == "사용자 수동 배치":
    st.subheader("✍️ 수동 배치 설정")
    m_cols = st.columns(num_elevators)
    active_placements = []
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f, key=f"v5_m_{i}")
            active_placements.append(val)

if not active_placements:
    active_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]

# [로직 수정] 배치 방식을 사용할 때는 분할 배치 가이드를 숨김
with st.container():
    if placement_option == "사용 안 함" and "분할 배치" in logic_option:
        st.markdown("""<style>.guide-box { background-color: #f0f7ff; padding: 15px; border-radius: 10px; border-left: 5px solid #0068c9; margin-bottom: 20px; }</style>""", unsafe_allow_html=True)
        mid_idx = (total_fs + idx_1f) // 2
        guide_text = f"""
        💡 **고층부 / 저층부 분할 배치 가이드** (배치 방식 미사용 시 적용)<br>
        - **저층부 구역 담당 (B{min_f} ~ {FLOOR_LABELS[mid_idx]}):** {', '.join([f'EL {chr(65+i)}' for i in range(num_elevators) if i < num_elevators/2])}<br>
        - **고층부 구역 담당 ({FLOOR_LABELS[mid_idx+1]} ~ {max_f}F):** {', '.join([f'EL {chr(65+i)}' for i in range(num_elevators) if i >= num_elevators/2])}
        """
        st.markdown(f'<div class="guide-box">{guide_text}</div>', unsafe_allow_html=True)

    st.write("### 현재 설정된 배치 상태:")
    disp_cols = st.columns(num_elevators)
    for i, p in enumerate(active_placements):
        disp_cols[i].metric(label=f"EL {chr(65+i)}", value=FLOOR_LABELS[p])
    st.divider()

# ----------------- [4] 시뮬레이션 엔진 -----------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route(start, end, placements, logic, cong, is_deliv, eff, base_t):
    w = {"매우 쾌적": 0.7, "보통": 1.1, "매우 혼잡": 2.5}[cong]
    avail = []
    for i in range(num_elevators):
        if "자유 운행" in logic: avail.append(i)
        elif "홀짝" in logic:
            if start <= idx_1f or (i % 2 == 0 and start % 2 != 0) or (i % 2 != 0 and start % 2 == 0): avail.append(i)
        elif "분할 배치" in logic:
            mid = (total_fs + idx_1f) // 2
            if start <= idx_1f or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid): avail.append(i)
    
    if not avail: avail = [0]
    min_dist_m = min([abs(placements[idx] - start) for idx in avail]) * floor_height
    wait_t = get_phys_time(min_dist_m, max_velocity, acceleration)
    move_t = get_phys_time(abs(start - end) * floor_height, max_velocity, acceleration)
    door_eff_t = base_t * (1 - (eff/100)) if start > idx_1f else base_t * 1.2
    total_t = (wait_t + move_t + (door_eff_t * w)) * (1.3 if is_deliv else 1.0)
    return total_t

# ----------------- [5] 결과 확인 및 꺽은선 그래프 -----------------
st.subheader("🌐 환경 설정 및 최종 시뮬레이션")
c_env1, c_env2 = st.columns(2)
with c_env1: congestion = st.select_slider("건물 혼잡도", options=["매우 쾌적", "보통", "매우 혼잡"], value="보통")
with c_env2: delivery_mode = st.toggle("📦 배송 지연 가중치 반영", value=current_is_deliv)

if st.button("🚀 전체 전략 분석 실행", type="primary", use_container_width=True):
    control_placements = [int(f) for f in np.linspace(0, total_fs-1, num_elevators)]
    avg_f = int(idx_1f + (max_f - 1) * 0.7)
    
    scenarios = {
        "1층 ⬆️ 거주층": (idx_1f, avg_f, lim_1f_up),
        "거주층 ⬇️ 1층": (avg_f, idx_1f, lim_res_1f),
        "주차장 ⬆️ 거주층": (0, avg_f, lim_p_up),
        "거주층 ⬇️ 주차장": (avg_f, 0, lim_res_p)
    }
    
    results = []
    m_cols = st.columns(4)
    for i, (name, (s, e, l)) in enumerate(scenarios.items()):
        t_base = simulate_route(s, e, control_placements, "자유 운행", congestion, delivery_mode, 0, base_door_time)
        t_strat = simulate_route(s, e, active_placements, logic_type, congestion, delivery_mode, button_efficiency, base_door_time)
        
        with m_cols[i]:
            diff = t_base - t_strat
            st.metric(name, f"{t_strat:.1f}s", delta=f"{diff:+.1f}s")
            if t_strat > l: st.error(f"SLA 미달 ({l}s)")
            else: st.success(f"SLA 통과 ({l}s)")
            
        results.append({"노선": name, "구분": "전략 미적용", "시간": t_base})
        results.append({"노선": name, "구분": "전략 적용", "시간": t_strat})

    df_res = pd.DataFrame(results)

    # [수정] 꺽은선 그래프 (Line Chart) 구현
    st.write("### 📈 노선별 시간 흐름 및 대조 (Line Chart)")
    line_chart = alt.Chart(df_res).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X('노선:N', title='분석 노선', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('시간:Q', title='소요 시간(초)'),
        color=alt.Color('구분:N', scale=alt.Scale(range=['#e74c3c', '#2ecc71']), title="전략 구분"),
        tooltip=['노선', '구분', '시간']
    ).properties(width=800, height=450).interactive()
    
    st.altair_chart(line_chart, use_container_width=True)

    # 데이터 요약
    st.write("### 📝 상세 시뮬레이션 데이터")
    df_p = df_res.pivot(index='노선', columns='구분', values='시간').reset_index()
    df_p['개선 시간(sec)'] = df_p['전략 미적용'] - df_p['전략 적용']
    df_p['개선 효율(%)'] = (df_p['개선 시간(sec)'] / df_p['전략 미적용'] * 100).fillna(0)
    
    st.dataframe(
        df_p.set_index('노선').style.format({
            "전략 미적용": "{:.2f}", "전략 적용": "{:.2f}",
            "개선 시간(sec)": "{:+.2f}", "개선 효율(%)": "{:.1f}%"
        }), use_container_width=True
    )
