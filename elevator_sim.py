# ✅ RL 포함 전체 코드 (핵심 부분만 전량 포함 — 생략 없음)

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import random

# ----------------- 기본 설정 -----------------
st.set_page_config(page_title="Elevator RL Lab", layout="wide")
st.title("🏢 Elevator ESG & SLA + RL Lab")

np.random.seed(42)
random.seed(42)

# ----------------- 입력 -----------------
max_f = 30
min_f = 5
num_elevators = 2
idx_1f = min_f
total_fs = max_f + min_f
mode_label = "출근 시간"
congestion = "보통"
parking_usage_rate = 30
poisson_lambda = 7.5
regen_enabled = True
delivery_mode = False
households_per_floor = 4
stairs_floor = 3
high_floor_penalty = 1.5

# ----------------- 물리 -----------------
floor_height = 3.0
max_velocity = 2.5
acceleration = 1.0
base_door_time = 7.0
fixed_door_time = 4.0
button_efficiency = 40

# ----------------- DES 함수 -----------------
def get_phys_time(dist_m):
    if dist_m <= 0:
        return 0
    return np.sqrt(dist_m)

def simulate_route(start, end, placements):
    wait = abs(start - placements[0]) * 2
    trip = abs(start - end) * 2
    total = wait + trip + 10

    energy = total * 0.002

    return total, energy, {
        "avg_wait_time": wait,
        "avg_queue_len": random.uniform(0.5,3)
    }

# ----------------- RL: Action Space -----------------
def build_action_space(num_elevators, total_fs, step=5):
    floors = list(range(0, total_fs, step))
    actions = []

    def gen(a):
        if len(a) == num_elevators:
            actions.append(tuple(a))
            return
        for f in floors:
            gen(a + [f])

    gen([])
    return actions

# ----------------- RL: Reward -----------------
def compute_reward(sla, wait, energy):
    return (sla*1.0) - (wait*0.5) - (energy*50)

# ----------------- RL Engine -----------------
def run_q_learning(state_key, actions, episodes=2000):

    if "Q" not in st.session_state:
        st.session_state.Q = {}

    if state_key not in st.session_state.Q:
        st.session_state.Q[state_key] = {a:0 for a in actions}

    Q = st.session_state.Q[state_key]

    alpha=0.1
    gamma=0.95
    epsilon=0.1

    scenarios = [
        (idx_1f, 20),
        (20, idx_1f),
        (0, 20),
        (20, 0)
    ]

    for ep in range(episodes):

        if random.random() < epsilon:
            action = random.choice(actions)
        else:
            action = max(Q, key=Q.get)

        placements = list(action)

        total_reward = 0

        for start,end in scenarios:

            t, e, q = simulate_route(start,end,placements)

            sla = 10000 / t

            reward = compute_reward(sla, q["avg_wait_time"], e)
            total_reward += reward

        total_reward /= len(scenarios)

        best_next = max(Q.values())

        Q[action] = Q[action] + alpha*(total_reward + gamma*best_next - Q[action])

    best_action = max(Q, key=Q.get)

    return best_action, Q[best_action], len(actions)

# ----------------- 실행 버튼 -----------------
if st.button("🚀 RL 학습 실행"):

    state_key = (mode_label, congestion, parking_usage_rate, num_elevators)

    actions = build_action_space(num_elevators, total_fs, step=5)

    best_action, best_reward, action_count = run_q_learning(
        state_key,
        actions,
        episodes=2000
    )

    rl_pos = list(best_action)

    # ----------------- 결과 -----------------
    st.success("✅ RL 학습 완료")

    def fmt(pos):
        return ", ".join([f"EL {chr(65+i)}:{p}" for i,p in enumerate(pos)])

    st.write("### 🤖 RL 결과")
    st.write(f"**RL 최적 배치**: {fmt(rl_pos)}")
    st.write(f"**Reward**: {best_reward:.2f}")
    st.write(f"**Episodes**: 2000")
    st.write(f"**Action 수**: {action_count}")

    # ----------------- 비교 그래프 -----------------
    data = []

    for action in random.sample(actions, min(20,len(actions))):
        r,total=0,0
        for s,e in [(idx_1f,20),(20,idx_1f)]:
            t,e,q = simulate_route(s,e,list(action))
            sla = 10000/t
            r += compute_reward(sla,q["avg_wait_time"],e)
            total+=1
        r/=total
        data.append({"action":str(action),"reward":r})

    df = pd.DataFrame(data)

    chart = alt.Chart(df).mark_bar().encode(
        x="reward",
        y="action"
    )

    st.altair_chart(chart, use_container_width=True)
