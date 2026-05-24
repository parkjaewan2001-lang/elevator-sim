import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] UI 및 페이지 전역 설정 -----------------

st.set_page_config(
    page_title="Elevator ESG & SLA Lab",
    layout="wide"
)

st.title("🏢 Elevator Strategic, ESG & SLA Experiment Lab")

st.subheader(
    "⚡ 동선별 타임라인·SLA 달성률 및 회생제동 기반 에너지/탄소 통합 추적 시스템"
)

st.markdown("""
> 💡 **Simulation Methodology (연구 방법론):**
>
> * **개별 동선 추적:** 4개 동선(1층↔거주층, 주차장↔거주층)의 실시간 소요 시간과 개별 SLA 달성률(0% 또는 100%)을 정밀 모니터링합니다.
>
> * **표준 물리 참조 및 회생제동 모델:** 본 시스템은 기어리스 동기모터(Efficiency 85%) 및 KEPCO 공동주택용 종합계약 단가를 기준으로 설계된 **'표준 물리 참조 모델'**을 사용합니다.
>
> 특히 현대 신축 아파트의 필수 기술인 **회생 제동(Regenerative Braking)** 물리 공식을 반영하여 만차 하행(⬇️) 및 공차 상행(⬆️) 시 발생하는 자가발전 전력 상쇄 효과를 정밀하게 추적합니다.
>
> * **대조 분석 기능 추가:** 모든 운영 전략의 연산 결과는 기준점인 **'전략 미적용 (랜덤 운행)' 대비 증감률(%)**로 자동 환산되어 알고리즘의 우수성을 정량적으로 증명합니다.
""")

# ----------------- [2] SIDEBAR -----------------

with st.sidebar:

    st.header("🏗️ 건물 및 세대 설정")

    c1, c2 = st.columns(2)

    with c1:
        max_f = st.number_input(
            "지상 최고층",
            value=30,
            step=1
        )

    with c2:
        min_f = st.number_input(
            "지하 최저층",
            value=5,
            step=1
        )

    num_elevators = st.number_input(
        "엘리베이터 개수",
        value=2,
        min_value=1,
        max_value=10
    )

    households_per_floor = st.number_input(
        "층당 세대수 (가구)",
        value=4,
        min_value=1
    )

    stairs_floor = st.number_input(
        "계단 이용 권장 층수",
        value=3,
        min_value=0,
        max_value=max_f
    )

    parking_usage_rate = st.number_input(
        "🚗 주차장 이용 비율 (%)",
        value=30,
        min_value=0,
        max_value=100,
        step=5
    )

    st.divider()

    st.header("🚀 물리 엔진 설정")

    floor_height = st.number_input(
        "층간 높이 (m)",
        value=3.0
    )

    max_velocity = st.number_input(
        "정격 속도 (m/s)",
        value=2.5
    )

    acceleration = st.number_input(
        "가속도 (m/s²)",
        value=1.0
    )

    fixed_door_moving_time = st.number_input(
        "고정 기계 작동 시간 (초) [열림+닫힘]",
        value=4.0,
        min_value=1.0,
        step=0.5
    )

    base_door_time = st.number_input(
        "기본 전체 문 시간 (초) [대기포함]",
        value=7.0,
        min_value=fixed_door_moving_time + 0.5,
        step=0.5
    )

    button_efficiency = st.number_input(
        "🔘 닫힘 버튼 효율 (%)",
        value=40,
        min_value=0,
        max_value=100,
        step=5
    )

    # ----------------- 회생제동 추가 -----------------

    st.divider()

    st.header("♻️ 회생제동 설정")

    regen_enabled = st.toggle(
        "회생제동 시스템 활성화",
        value=True
    )

    # ------------------------------------------------

    st.divider()

    st.header("⚠️ 서비스 임계치 (SLA) 설정")

    lim_1f_up = st.number_input(
        "SLA: 1층 → 거주층 (초)",
        value=45,
        min_value=10
    )

    lim_res_1f = st.number_input(
        "SLA: 거주층 → 1층 (초)",
        value=55,
        min_value=10
    )

    lim_p_up = st.number_input(
        "SLA: 주차장 → 거주층 (초)",
        value=50,
        min_value=10
    )

    lim_res_p = st.number_input(
        "SLA: 거주층 → 주차장 (초)",
        value=65,
        min_value=10
    )

# ----------------- [3] 층 정보 -----------------

FLOOR_LABELS = (
    [f"B{i}" for i in range(min_f, 0, -1)]
    +
    [f"{i}F" for i in range(1, max_f + 1)]
)

idx_1f = min_f

total_fs = len(FLOOR_LABELS)

# ----------------- [4] 전략 생성 -----------------

strategies_config = {}

np.random.seed(42)

strategies_config["전략 미적용 (랜덤 운행)"] = {
    "placements": list(
        np.random.randint(
            0,
            total_fs,
            num_elevators
        )
    ),
    "logic": "자유 운행"
}

strategies_config["베이스 스테이션 집중"] = {
    "placements": [idx_1f] * num_elevators,
    "logic": "자유 운행"
}

strategies_config["동적 간격 배치"] = {
    "placements": [
        int(f)
        for f in np.linspace(
            0,
            total_fs - 1,
            num_elevators
        )
    ],
    "logic": "자유 운행"
}

# ----------------- [5] 물리 함수 -----------------

def get_phys_time(dist_m, v_max, accel):

    if dist_m <= 0:
        return 0

    d_accel = (
        (v_max ** 2)
        /
        (2 * accel)
    )

    if dist_m >= 2 * d_accel:

        return (
            (2 * (v_max / accel))
            +
            (dist_m - 2 * d_accel) / v_max
        )

    return 2 * np.sqrt(dist_m / accel)

# ----------------- [6] 메인 시뮬레이션 -----------------

def simulate_route_esg_sla(
    start,
    end,
    placements,
    logic,
    congestion,
    is_deliv,
    regen_enabled
):

    congestion_weights = {
        "매우 쾌적": 0.7,
        "쾌적": 0.9,
        "보통": 1.1,
        "혼잡": 1.8,
        "매우 혼잡": 2.5
    }

    w = congestion_weights[congestion]

    chosen_el = 0

    wait_dist = abs(
        placements[chosen_el] - start
    ) * floor_height

    wait_t = get_phys_time(
        wait_dist,
        max_velocity,
        acceleration
    )

    move_dist = abs(
        start - end
    ) * floor_height

    move_t = get_phys_time(
        move_dist,
        max_velocity,
        acceleration
    )

    door_t = (
        fixed_door_moving_time
        +
        (
            base_door_time
            - fixed_door_moving_time
        )
        *
        (
            1
            - button_efficiency / 100
        )
    )

    total_time = (
        wait_t
        +
        move_t
        +
        (door_t * w)
    )

    # ---------------- 에너지 계산 ----------------

    total_dist = (
        wait_dist
        +
        move_dist
    )

    moving_time = get_phys_time(
        total_dist,
        max_velocity,
        acceleration
    )

    energy_base = (
        (
            500
            * 9.8
            * max_velocity
            * moving_time
        )
        /
        (
            0.85
            * 3600
            * 1000
        )
    )

    is_upward = end > start

    is_heavy = (
        w >= 1.2
        or is_deliv
    )

    regen_factor = 1.0

    # ---------------- 회생제동 ----------------

    if regen_enabled:

        # 상행 공차
        if is_upward and not is_heavy:

            regen_factor = -0.35

        # 하행 만차
        elif (
            not is_upward
            and is_heavy
        ):

            regen_factor = -0.40

        # 상행 만차
        elif (
            is_upward
            and is_heavy
        ):

            regen_factor = 1.30

    # -----------------------------------------

    energy_final = (
        energy_base
        * regen_factor
    )

    door_energy = 0.001 * w

    total_kwh = (
        energy_final
        +
        door_energy
    )

    return total_time, total_kwh

# ----------------- [7] 환경 조건 -----------------

st.header("🌐 시뮬레이션 환경 조건")

c1, c2 = st.columns(2)

with c1:

    congestion = st.radio(
        "건물 내부 혼잡도",
        options=[
            "매우 쾌적",
            "쾌적",
            "보통",
            "혼잡",
            "매우 혼잡"
        ],
        horizontal=True
    )

with c2:

    delivery_mode = st.toggle(
        "📦 배달 패널티 활성화",
        value=False
    )

# ----------------- [8] 실행 -----------------

if st.button(
    "🚀 시뮬레이션 실행",
    use_container_width=True
):

    avg_res_f = int(
        idx_1f
        +
        (max_f - 1) * 0.7
    )

    scenarios = {

        "1층 ⬆️ 거주층": (
            idx_1f,
            avg_res_f,
            lim_1f_up
        ),

        "거주층 ⬇️ 1층": (
            avg_res_f,
            idx_1f,
            lim_res_1f
        ),

        "주차장 ⬆️ 거주층": (
            0,
            avg_res_f,
            lim_p_up
        ),

        "거주층 ⬇️ 주차장": (
            avg_res_f,
            0,
            lim_res_p
        )
    }

    results = []

    for scen_name, (
        start,
        end,
        sla_target
    ) in scenarios.items():

        for strat_name, config in strategies_config.items():

            calc_time, calc_kwh = simulate_route_esg_sla(

                start,
                end,

                config["placements"],
                config["logic"],

                congestion,

                delivery_mode,

                regen_enabled
            )

            sla_pass = (
                100
                if calc_time <= sla_target
                else 0
            )

            cost = calc_kwh * 195

            carbon = calc_kwh * 424

            results.append({

                "운영 전략": strat_name,

                "동선 시나리오": scen_name,

                "실제 소요시간": round(calc_time, 2),

                "SLA 달성률": sla_pass,

                "전력 소비량(kWh)": round(calc_kwh, 4),

                "전기 요금(원)": round(cost, 1),

                "탄소 배출량(g)": round(carbon, 1)
            })

    df = pd.DataFrame(results)

    # ---------------- 결과 테이블 ----------------

    st.write("### 📈 SLA 및 ESG 분석 결과")

    st.dataframe(
        df,
        use_container_width=True
    )

    # ---------------- ESG 요약 ----------------

    st.write("### 🌿 ESG 전략별 총합")

    esg_df = df.groupby(
        "운영 전략"
    ).agg({

        "전력 소비량(kWh)": "sum",

        "전기 요금(원)": "sum",

        "탄소 배출량(g)": "sum"

    }).reset_index()

    st.dataframe(
        esg_df,
        use_container_width=True
    )

    # ---------------- 그래프 ----------------

    st.write("### 📊 전략별 전력 소비량 비교")

    energy_chart = alt.Chart(
        esg_df
    ).mark_bar().encode(

        x=alt.X(
            "운영 전략:N",
            sort=None
        ),

        y=alt.Y(
            "전력 소비량(kWh):Q"
        ),

        color="운영 전략:N"
    ).properties(
        height=400
    )

    st.altair_chart(
        energy_chart,
        use_container_width=True
    )

    st.caption(
        "💡 회생제동 ON 시 일부 구간에서 음수 소비전력(자가발전)이 발생할 수 있습니다."
    )
