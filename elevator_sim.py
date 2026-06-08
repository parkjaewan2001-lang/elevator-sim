import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from dataclasses import dataclass
import random

# ----------------- [1] UI 및 페이지 전역 설정 -----------------
st.set_page_config(page_title="Elevator ESG & SLA Lab", layout="wide")
st.title("🏢 Elevator Strategic, ESG & SLA Experiment Lab")
st.subheader("⚡ 동선별 타임라인·SLA 달성률 및 회생제동 기반 에너지/탄소 통합 추적 시스템")

st.markdown("""
> 💡 **Simulation Methodology (연구 방법론):**
> * **개별 동선 추적:** 4개 동선(1층↔거주층, 주차장↔거주층)의 실시간 소요 시간과 개별 SLA 달성률을 정밀 모니터링합니다.
> * **DES Event-Driven 구조:** 승객 호출 대기열(Queue)이 쌓이면 엘리베이터가 `호출 → 배정 → 출발층 도착 → 탑승 → 목적지 하차`의 이벤트를 순차적으로 처리합니다.
> * **시간대별 수요 가중치:** 출근 시간은 `주거층 → 1층/B1`, 퇴근 시간은 `1층/B1 → 주거층` 호출이 높은 확률로 발생하도록 반영합니다.
> * **Queue 지표 추가:** 모든 운영 전략별로 평균 대기시간, 최대 대기시간, 평균 Queue 길이를 산출합니다.
> * **표준 물리 참조 및 회생제동 모델:** 기어리스 동기모터(Efficiency 85%) 및 KEPCO 요금제 기준.
> * **대조 분석 기능:** 모든 전략의 연산 결과는 기준점인 **'전략 미적용 (랜덤 운행)' 대비 증감률(%)**로 자동 환산됩니다.
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
        min_value=1.0,
        max_value=20.0,
        value=7.5,
        step=0.5,
        help="값이 높을수록 앞선 호출이 밀려 대기 시간이 늘어나는 병목 현상이 강해집니다."
    )

    high_floor_penalty = st.number_input(
        "고층부 대기 패널티 계수",
        min_value=1.0,
        max_value=3.0,
        value=1.5,
        step=0.1,
        help="고층일수록 엘리베이터를 놓쳤을 때 발생하는 체감 대기시간 증가율입니다."
    )

    st.divider()
    st.header("🌱 ESG 하드웨어 옵션")
    regen_enabled = st.toggle(
        "🔄 회생제동(Regen) 인버터 활성화",
        value=True,
        help="끄면 회생전력이 발전되지 않고 열로 방출되는 구축 아파트 상태가 됩니다."
    )

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
            val = st.selectbox(
                f"EL {chr(65 + i)}",
                options=range(total_fs),
                format_func=lambda x: FLOOR_LABELS[x],
                index=idx_1f,
                key=f"v_percent_metrics_{i}"
            )
            manual_placements.append(val)

st.divider()

# ----------------- 운영 전략 대기 포지션 맵 빌드 -----------------
strategies_config = {}
np.random.seed(42)

strategies_config["전략 미적용 (랜덤 운행)"] = {
    "placements": list(np.random.randint(0, total_fs, num_elevators)),
    "logic": "자유 운행",
    "desc": "무작위 방치 상태"
}

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
    "desc": "홀/짝수층 전담 정차로 감속 손실 방지"
}

mid_idx = (total_fs + idx_1f) // 2
if num_elevators == 1:
    split_placements = [mid_idx]
else:
    split_placements = [
        int(idx_1f + (mid_idx - idx_1f) / 2) if i < num_elevators / 2
        else int(mid_idx + (total_fs - mid_idx) / 2)
        for i in range(num_elevators)
    ]

strategies_config["고층부/저층부 분할배치"] = {
    "placements": split_placements,
    "logic": "분할 배치",
    "desc": "건물 상/하방 구역 분할 대기"
}

strategies_config["베이스 스테이션 집중"] = {
    "placements": [idx_1f] * num_elevators,
    "logic": "베이스 스테이션 집중",
    "desc": "운행 종료 후 무조건 1층 로비 복귀"
}

if num_elevators == 1:
    spacing_placements = [mid_idx]
else:
    spacing_placements = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]

strategies_config["동적 간격 배치"] = {
    "placements": spacing_placements,
    "logic": "자유 운행",
    "desc": "전체 가용 층수에 등간격 분산 대기"
}

if mode_label == "새벽 시간":
    if num_elevators > 1:
        ai_pos = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2)
    else:
        ai_pos = [idx_1f]
elif mode_label == "출근 시간":
