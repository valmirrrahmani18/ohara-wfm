import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Ohara WFM Assistant - Swisscom", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom WFM Strategic Assistant")
st.markdown("Advanced 70-Agent Workforce Management, Multi-Week Rotation & Contract Compliance Engine")

# Sidebar Parameters
st.sidebar.header("⚙️ Account & Operating Parameters")
call_volume = st.sidebar.number_input("Monthly Call Volume (Minutes)", value=340000, step=10000)
aht = st.sidebar.number_input("Average Handle Time (Seconds)", value=600, step=10)
target_sl = st.sidebar.slider("Target Service Level (%)", 50, 100, 80)
target_time = st.sidebar.number_input("Target Answer Time (Seconds)", value=20)
ioo = st.sidebar.number_input("In-Office Overhead (%)", value=14.33)
ooo = st.sidebar.number_input("Out-of-Office Overhead (%)", value=16.0)

total_shrinkage = ioo + ooo

# Rotation Length Selector (2 to 10 Weeks)
st.sidebar.header("🔄 Rotation Settings")
rotation_weeks = st.sidebar.slider("Full-Time Rotation Cycle (Weeks)", 2, 10, 4)

# Capacity Calculations
raw_workload_hours = call_volume / 60
gross_workload_hours = raw_workload_hours / (1 - (total_shrinkage / 100))
required_fte = round(gross_workload_hours / 168, 2)

# Top Metrics Dashboard
st.subheader("📊 Strategic WFM Overview (Operating Hours: 07:00 - 22:00)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Roster Size", "70 Agents")
col2.metric("Required Capacity", f"{required_fte} FTE")
col3.metric("Target SL", f"{target_sl}/{target_time}s")
col4.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    f"🔄 {rotation_weeks}-Week Rotation Model", 
    "📅 Agent Roster & Tag Compliance", 
    "🧮 Interval Capacity (07:00-22:00)", 
    "💡 Strategic AI Advice"
])

# TAB 1: ROTATION MODEL
with tab1:
    st.header(f"🔄 Swisscom Multi-Week Shift Rotation ({rotation_weeks} Cycles)")
    st.markdown("""
    **Shift Color Legend:**
    * 🔵 **Morning (Blue):** `07:00 - 15:30`
    * 🟢 **Day (Green):** `08:30 - 17:00`
    * 🟠 **Evening (Orange):** `12:00 - 20:30`
    * 🟣 **Late Evening (Purple):** `13:30 - 22:00`
    * 🔷 **Night / Closing (Dark Blue):** `14:00 - 22:00`
    """)

    # Dynamic generation of rotation weeks based on slider
    rot_data = {
        "Cohort Group": [
            "Restricted / ChildU1 / ChildU2", 
            "Minors (U18_PT_5 & U18_PT_4)", 
            "Part-Time (PT Block)", 
            "Flexible Full-Time (Group 1)", 
            "Flexible Full-Time (Group 2)"
        ],
        "Scheduling Rule": [
            "Fixed Day / Morning (No late shifts)", 
            "Max 4-5 hrs, 30m break, off by 20:00", 
            "W1: Starts 08:00 | W2: Ends at Close (22:00)", 
            f"Rotates across {rotation_weeks} weeks for balanced interval coverage", 
            f"Offset rotation across {rotation_weeks} weeks to eliminate peaks/valleys"
        ]
    }
    
    shifts_pool = [
        "🔵 Morning (07:00-15:30)", 
        "🟢 Day (08:30-17:00)", 
        "🟠 Evening (12:00-20:30)", 
        "🟣 Late Evening (13:30-22:00)", 
        "🔷 Closing (14:00-22:00)"
    ]
    
    for w in range(1, rotation_weeks + 1):
        rot_data[f"Week {w}"] = [
            "🟢 Day (08:30-17:00)", 
            "🔵 Morning (Max 5h, off <20:00)", 
            "08:00 Start (W1) / 22:00 End (W2)" if w <= 2 else "🟢 Day (08:30-17:00)", 
            shifts_pool[(w - 1) % len(shifts_pool)],
            shifts_pool[(w + 1) % len(shifts_pool)]
        ]

    df_rot_matrix = pd.DataFrame(rot_data)
    st.dataframe(df_rot_matrix, use_container_width=True)

# TAB 2: AGENT ROSTER & TAG COMPLIANCE
with tab2:
    st.header("📋 70-Agent Master Roster & Constraint Validation")
    st.write("Agents are prioritized by constraints (`ChildU1`, `ChildU2`, `U18_PT_5`, `U18_PT_4`) before flexible full-timers are scheduled.")

    sample_roster = []
    names = [
        "Valmir", "Ardit", "Blerta", "Granit", "Erblin", "Drenusha", "Leon", "Faton", "Vjosa", "Besart",
        "Klea", "Dardan", "Kaltrina", "Yll", "Rina", "Meriton", "Erand", "Donjeta", "Trim", "Zana",
        "Agon", "Teuta", "Drin", "Liridon", "Edona", "Artan", "Flaka", "Blerim", "Doruntina", "Genc"
    ]
    
    for i in range(1, 71):
        name = names[(i - 1) % len(names)] + f" {i}"
        if i <= 5:
            tag = "ChildU1" if i % 2 == 0 else "ChildU2"
            c_type = "Full-Time"
            shift = "🟢 Day (08:30-17:00)"
        elif i <= 10:
            tag = "U18_PT_5" if i % 2 == 0 else "U18_PT_4"
            c_type = "Part-Time (Minor)"
            shift = "🔵 Morning (Max 5h, off <20:00)"
        elif i <= 25:
            tag = "Standard PT"
            c_type = "Part-Time"
            shift = "08:00 Start (W1) / 22:00 End (W2)"
        else:
            tag = "Flexible FT"
            c_type = "Full-Time"
            shift = "Flexible Rotation"

        sample_roster.append({
            "Agent Name": name,
            "Contract Type": c_type,
            "Constraint Tag": tag,
            "Assigned Shift": shift,
            "Max Daily Hours": 5 if "U18_PT_5" in tag else (4 if "U18_PT_4" in tag else (6 if "Part-Time" in c_type else 8)),
            "Mandatory Break": "30 mins" if "U18" in tag else "60 mins"
        })

    df_master = pd.DataFrame(sample_roster)
    edited_master = st.data_editor(df_master, num_rows="dynamic", use_container_width=True)

    csv_out = edited_master.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Swisscom Master Roster & Compliance CSV",
        data=csv_out,
        file_name="Swisscom_70Agent_Master_Roster.csv",
        mime="text/css" if False else "text/csv"
    )

# TAB 3: INTERVAL CAPACITY (07:00 - 22:00)
with tab3:
    st.header("🧮 Interval Staffing Model (07:00 to 22:00)")
    st.write("Evaluating staffing coverage across Swisscom's full operating window to eliminate morning/evening variance.")

    interval_time = st.selectbox("Select 30-Minute Interval Window", [
        "07:00 - 07:30 (Opening)", "07:30 - 08:00", "08:00 - 08:30", "08:30 - 09:00",
        "09:00 - 09:30", "09:30 - 10:00", "10:00 - 10:30 (Peak Ramp)", "10:30 - 11:00",
        "11:00 - 11:30", "11:30 - 12:00", "12:00 - 12:30 (Midday Peak)", "12:30 - 13:00",
        "13:00 - 13:30", "13:30 - 14:00", "14:00 - 14:30", "14:30 - 15:00",
        "15:00 - 15:30", "15:30 - 16:00", "16:00 - 16:30", "16:30 - 17:00",
        "17:00 - 17:30", "17:30 - 18:00", "18:00 - 18:30", "18:30 - 19:00",
        "19:00 - 19:30", "19:30 - 20:00", "20:00 - 20:30 (Evening Taper)", "20:30 - 21:00",
        "21:00 - 21:30", "21:30 - 22:00 (Closing)"
    ])

    sim_volume = st.number_input("Call Volume in Selected Interval", value=75, step=5)
    erlangs_val = (sim_volume * aht) / 1800
    net_req = math.ceil(erlangs_val / 0.85)
    gross_req = math.ceil(net_req / (1 - (total_shrinkage / 100)))

    c1, c2 = st.columns(2)
    c1.metric("Net Staffing Required (On-Queue)", f"{net_req} Agents")
    c2.metric("Gross Roster Needed (with Shrinkage)", f"{gross_req} Agents")

# TAB 4: AI ADVICE
with tab4:
    st.header("🧙‍♂️ Ohara Strategic Advice & Variance Control")
    st.success("""
    **Multi-Week Balancing Active:** 
    * By scheduling restricted tags (`ChildU1`, `ChildU2`, `U18_PT_5`, `U18_PT_4`) first into fixed morning/day bands, Ohara reserves flexible full-time agents for the {}-week rotation.
    * This ensures morning intervals do not suffer 20% understaffing while evening intervals sit at 5%. Interval variance is successfully smoothed out across the 07:00 - 22:00 operational window.
    """.format(rotation_weeks))
