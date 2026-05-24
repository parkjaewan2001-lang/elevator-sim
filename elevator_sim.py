# ----------------- [2] SIDEBAR: 설정 변수 -----------------

with st.sidebar:

    st.header("🏗️ 건물 및 세대 설정")

    c1, c2 = st.columns(2)

    with c1:
        max_f = st.number_input("지상 최고층", value=30, step=1)

    with c2:
        min_f = st.number_input("지하 최저층", value=5, step=1)

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

    # ---------------- 추가된 부분 ----------------
    st.divider()

    st.header("♻️ 회생제동 설정")

    regen_enabled = st.toggle(
        "회생제동 시스템 활성화",
        value=True
    )
    # ------------------------------------------------
