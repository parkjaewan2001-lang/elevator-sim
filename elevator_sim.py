import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ----------------- [1] UI & Global Configuration -----------------
st.set_page_config(page_title="Elevator ESG & SLA Lab", layout="wide")
st.title("🏢 Elevator Strategic, ESG & SLA Experiment Lab")
st.subheader("⚡ System Metric Dashboard & Energy Regen Tracking Engine")

st.markdown("""
> 💡 **Simulation Methodology:**
> * **Route Tracking:** Monitors real-time travel duration and SLA success rate for 4 distinct paths.
> * **ESG Hardware Option:** Toggle 'Regen Inverter' in the sidebar to compare a Modern Building (ON) vs Legacy Building (OFF).
> * **Delta Comparison:** All results automatically display percentage variance (%) relative to the 'Baseline Strategy'.
""")

# ----------------- [2] SIDEBAR: Control Variables -----------------
with st.sidebar:
    st.header("🏗️ Building & Unit Settings")
    c1, c2 = st.columns(2)
    with c1: max_f = st.number_input("Max Floor (Top)", value=30, step=1)
    with c2: min_f = st.number_input("Min Floor (Lowest B)", value=5, step=1)
    
    num_elevators = st.number_input("Number of Elevators", value=2, min_value=1, max_value=10)
    households_per_floor = st.number_input("Households per Floor", value=4, min_value=1)
    stairs_floor = st.number_input("Recommended Stairs Threshold", value=3, min_value=0, max_value=max_f)
    parking_usage_rate = st.number_input("Parking Lot Usage Rate (%)", value=30, min_value=0, max_value=100, step=5)

    st.divider()
    st.header("🌱 ESG Hardware Configuration")
    regen_enabled = st.toggle("Regen Inverter Active", value=True, help="If OFF, braking energy is wasted as heat (Legacy Infrastructure).")

    st.divider()
    st.header("🚀 Physics Engine Tuning")
    floor_height = st.number_input("Floor Height (m)", value=3.0)
    max_velocity = st.number_input("Rated Velocity (m/s)", value=2.5)
    acceleration = st.number_input("Acceleration (m/s²)", value=1.0)
    
    fixed_door_moving_time = st.number_input("Mechanical Door Time (s) [Open+Close]", value=4.0, min_value=1.0, step=0.5)
    base_door_time = st.number_input("Total Dwell Time (s) [Include Wait]", value=7.0, min_value=fixed_door_moving_time + 0.5, step=0.5)
    button_efficiency = st.number_input("Close Button Efficiency (%)", value=40, min_value=0, max_value=100, step=5)
    
    pure_dwell_time = max(0.0, base_door_time - fixed_door_moving_time)
    saved_door_time = pure_dwell_time * (button_efficiency / 100)
    final_door_operating_time = base_door_time - saved_door_time

    st.divider()
    st.header("⚠️ Service Level Agreement (SLA)")
    lim_1f_up = st.number_input("SLA Target: 1F -> Resident (s)", value=45, min_value=10)
    lim_res_1f = st.number_input("SLA Target: Resident -> 1F (s)", value=55, min_value=10)
    lim_p_up = st.number_input("SLA Target: Parking -> Resident (s)", value=50, min_value=10)
    lim_res_p = st.number_input("SLA Target: Resident -> Parking (s)", value=65, min_value=10)

# ----------------- [3] MAIN: Input Patterns -----------------
FLOOR_LABELS = [f"B{i}" for i in range(min_f, 0, -1)] + [f"{i}F" for i in range(1, max_f + 1)]
idx_1f = min_f 
total_fs = len(FLOOR_LABELS)

st.header("⚙️ Simulation Timeline & Manual Placement")
c_time, c_custom = st.columns([1, 1])

with c_time:
    st.write("##### Time Pattern Selection")
    time_options = [
        "Midnight (00-06) [Rate: 78 KRW/kWh]", 
        "Rush-Hour (07-09) [Rate: 195 KRW/kWh]", 
        "Daytime (09-18) [Rate: 132 KRW/kWh]", 
        "Evening-Peak (18-20) [Rate: 195 KRW/kWh]", 
        "Night (20-23) [Rate: 195 KRW/kWh]"
    ]
    mode_selection = st.radio("Time Zone Settings", options=time_options, index=1, horizontal=False)
    mode_label = mode_selection.split(" (")[0]
    current_is_deliv = True if "Midnight" in mode_selection else False
    
    if "78 KRW" in mode_selection:
        kepco_rate = 78.0
    elif "132 KRW" in mode_selection:
        kepco_rate = 132.0
    else:
        kepco_rate = 195.0

with c_custom:
    st.write("##### Manual Car Allocation")
    m_cols = st.columns(num_elevators)
    manual_placements = []
    for i in range(num_elevators):
        with m_cols[i]:
            val = st.selectbox(f"EL {chr(65+i)}", options=range(total_fs), format_func=lambda x: FLOOR_LABELS[x], index=idx_1f, key=f"v_pure_eng_{i}")
            manual_placements.append(val)

st.divider()

# --- Dispatch Strategy Profile Configuration ---
BASE_ID = "BASE"
STRAT_MAP = {
    BASE_ID: "Baseline Strategy (Random Dispatch)",
    "ODD_EVEN": "Odd/Even Floor Zoning Strategy",
    "ZONE_SPLIT": "High/Low Sector Split Strategy",
    "BASE_RETURN": "Base Station (1F) Forced Return",
    "DYNAMIC_GAP": "Equidistant Dynamic Gap Strategy",
    "AI_OPTIM": f"AI Predictive Positioning ({mode_label})",
    "MANUAL": "User-Defined Custom Allocation"
}

strategies_config = {}
np.random.seed(42) 

strategies_config[BASE_ID] = {"placements": list(np.random.randint(0, total_fs, num_elevators)), "logic": "Free"}

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
strategies_config["ODD_EVEN"] = {"placements": oe_placements, "logic": "Zoning"}

mid_idx = (total_fs + idx_1f) // 2
if num_elevators == 1:
    split_placements = [mid_idx]
else:
    split_placements = [int(idx_1f + (mid_idx-idx_1f)/2) if i < num_elevators/2 else int(mid_idx + (total_fs-mid_idx)/2) for i in range(num_elevators)]
strategies_config["ZONE_SPLIT"] = {"placements": split_placements, "logic": "Split"}

strategies_config["BASE_RETURN"] = {"placements": [idx_1f] * num_elevators, "logic": "Free"}

if num_elevators == 1:
    spacing_placements = [mid_idx]
else:
    spacing_placements = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config["DYNAMIC_GAP"] = {"placements": spacing_placements, "logic": "Free"}

if "Midnight" in mode_label:
    ai_pos = [idx_1f] * (num_elevators // 2) + [0] * (num_elevators - num_elevators // 2) if num_elevators > 1 else [idx_1f]
elif "Rush-Hour" in mode_label:
    res_start = idx_1f + stairs_floor + 1
    res_end = total_fs - 1
    ai_pos = [int(res_start + (res_end - res_start) * (i + 1) / (num_elevators + 1)) if res_start < res_end else res_end for i in range(num_elevators)]
elif "Evening-Peak" in mode_label:
    p_count = int(round(num_elevators * (parking_usage_rate / 100)))
    ai_pos = [0] * p_count + [idx_1f] * (num_elevators - p_count)
elif "Night" in mode_label:
    lower_mid_f = int(idx_1f + (total_fs - idx_1f) * 0.3)
    ai_pos = []
    for i in range(num_elevators):
        if i % 2 == 0:
            ai_pos.append(idx_1f)
        else:
            ai_pos.append(lower_mid_f)
else:
    ai_pos = [int(f) for f in np.linspace(0, total_fs - 1, num_elevators)]
strategies_config["AI_OPTIM"] = {"placements": ai_pos, "logic": "Free"}

strategies_config["MANUAL"] = {"placements": manual_placements, "logic": "Free"}

# ----------------- [4] Physics Engine Core -----------------
def get_phys_time(dist_m, v_max, accel):
    if dist_m <= 0: return 0
    d_accel = (v_max**2) / (2 * accel)
    if dist_m >= 2 * d_accel: return (2 * (v_max / accel)) + (dist_m - 2 * d_accel) / v_max
    return 2 * np.sqrt(dist_m / accel)

def simulate_route_esg_sla(start, end, placements, logic, cong, is_deliv, eff, base_t, fixed_t, p_rate, s_floor, households, is_regen_on):
    if abs(start - end) <= s_floor and start >= idx_1f:
        return 5.0, 0.001
    
    congestion_weights = {"Very Clean": 0.7, "Clean": 0.9, "Normal": 1.1, "Crowded": 1.8, "Heavy Traffic": 2.5}
    current_cong = "Normal" if cong not in congestion_weights else cong
    w = congestion_weights[current_cong] * (1.0 + (households - 1) * 0.05)
    
    if is_deliv:
        w = w * 1.5
        delivery_stops_penalty = 2.4
        door_holding_penalty = 1.8
    else:
        delivery_stops_penalty = 1.0
        door_holding_penalty = 1.0
    
    avail = [i for i in range(num_elevators)]
    if num_elevators > 1:
        if "Zoning" in logic:
            avail = [i for i in avail if start <= idx_1f or (i % 2 == 0 and start % 2 != 0) or (i % 2 != 0 and start % 2 == 0)]
        elif "Split" in logic:
            mid = (total_fs + idx_1f) // 2
            avail = [i for i in avail if start <= idx_1f or (i < num_elevators/2 and start <= mid) or (i >= num_elevators/2 and start > mid)]
    if not avail: avail = [0]
    
    chosen_el_idx = avail[0]
    min_dist_m = abs(placements[chosen_el_idx] - start) * floor_height
    wait_t = get_phys_time(min_dist_m, max_velocity, acceleration)
    
    if logic == "BASE_RETURN" and start != idx_1f:
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
    energy_move_base = ((500 * 9.8 * max_velocity * moving_time_pure) / (0.85 * 3600 * 1000)) * delivery_stops_penalty
    
    is_upward = (end > start)
    is_heavy_load = (w >= 1.2 or is_deliv)
    
    regen_factor = 1.0
    if is_regen_on:
        if is_upward and not is_heavy_load:
            regen_factor = -0.35
        elif not is_upward and is_heavy_load:
            regen_factor = -0.40
        elif is_upward and is_heavy_load:
            regen_factor = 1.30
    else:
        if is_upward and is_heavy_load:
            regen_factor = 1.30
        else:
            regen_factor = 0.05
        
    energy_move_final = energy_move_base * regen_factor
    energy_door = 0.001 * w * door_holding_penalty
    total_kwh = energy_move_final + energy_door
    
    return final_time, total_kwh

# ----------------- [5] Execution Interface -----------------
st.subheader("🌐 Simulation Control Desk")

c_env1, c_env2 = st.columns(2)
with c_env1: 
    congestion = st.radio("Congestion Dynamic Level", options=["Very Clean", "Clean", "Normal", "Crowded", "Heavy Traffic"], index=2, horizontal=True)
with c_env2: 
    delivery_mode = st.toggle("Delivery Courier Penalty Active", value=current_is_deliv)

infra_msg = "Infrastructure System Status: SMART REGEN ON" if regen_enabled else "Infrastructure System Status: TRADITIONAL HEAT-WASTE"
st.info(infra_msg)

if 'sim_run' not in st.session_state:
    st.session_state.sim_run = False
if 'matrix_data' not in st.session_state:
    st.session_state.matrix_data = None

if st.button("🚀 EXECUTE SYSTEM STRATEGY SIMULATION", type="primary", use_container_width=True):
    avg_res_f = int(idx_1f + (max_f - 1) * 0.7)
    
    scenarios_config = {
        "ROUTE_1F_UP": (idx_1f, avg_res_f, lim_1f_up, "1F -> Resident"),
        "ROUTE_RES_1F": (avg_res_f, idx_1f, lim_res_1f, "Resident -> 1F"),
        "ROUTE_P_UP": (0, avg_res_f, lim_p_up, "Parking -> Resident"),
        "ROUTE_RES_P": (avg_res_f, 0, lim_res_p, "Resident -> Parking")
    }
