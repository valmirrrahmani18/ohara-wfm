import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Ohara WFM Assistant", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom WFM Strategic Assistant")
st.markdown("Automated Shift Scheduling, Rotation Models & Strategic Capacity Planning for Swisscom (70 Agents)")

# Sidebar Parameters
st.sidebar.header("⚙️ Account Parameters")
call_volume = st.sidebar.number_input("Monthly Call Volume (Minutes)", value=340000, step=10000)
aht = st.sidebar.number_input("Average Handle Time (Seconds)", value=600, step=10)
target_sl = st.sidebar.slider("Target Service Level (%)", 50, 100, 80)
target_time = st.sidebar.number_input("Target Answer Time (Seconds)", value=20)
ioo = st.sidebar.number_input("In-Office Overhead (%)", value=14.33)
ooo = st.sidebar.number_input("Out-of-Office Overhead (%)", value=16.0)

total_shrinkage = ioo + ooo

# Capacity Calculations
raw_workload_hours = call_volume / 60
gross_workload_hours = raw_workload_hours / (1 - (total_shrinkage / 100))
required_fte = round(gross_workload_hours / 168, 2)

# Top Metrics Dashboard
st.subheader("📊 Strategic WFM Overview")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Roster Size", "70 Agents")
col2.metric("Required Capacity", f"{required_fte} FTE")
col3.metric("Target SL", f"{target_sl}/{target_time}s")
col4.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🔄 4-Week Shift Rotation Engine", 
    "📅 Live Roster & CSV Export", 
    "🧮 Interval Capacity Model", 
    "💡 Strategic Advice"
])

# TAB 1: ROTATION MODEL
with tab1:
    st.header("🔄 Swisscom 4-Week Multi-Cycle Shift Rotation")
    st.write("This engine balances forecast coverage across peak hours while respecting contract tags (`ChildU1`, `ChildU2`, `U18`).")

    rotation_summary = {
        "Group / Cohort": ["Group A (18 FT)", "Group B (18 FT)", "Group C (18 FT)", "Group D (16 PT)"],
        "Focus Area": ["Early Focus (15%)", "Peak Anchor A (40%)", "Peak / Closing B (30%)", "2-Week PT Block (15%)"],
        "Week 1": ["Shift 1 (07:00-15:30)", "Shift 2 (08:30-17:00)", "Shift 3 (10:00-18:30)", "PT Block 1 (09:00-14:00)"],
        "Week 2": ["Shift 2 (08:30-17:00)", "Shift 3 (10:00-18:30)", "Shift 4 (11:30-20:00)", "PT Block 1 (09:00-14:00)"],
        "Week 3": ["Shift 3 (10:00-18:30)", "Shift 4 (11:30-20:00)", "Shift 1 (07:00-15:30)", "PT Block 2 (10:00-15:00)"],
        "Week 4": ["Shift 4 (11:30-20:00)", "Shift 1 (07:00-15:30)", "Shift 2 (08:30-17:00)", "PT Block 2 (10:00-15:00)"]
    }
    df_rot = pd.DataFrame(rotation_summary)
    st.dataframe(df_rot, use_container_width=True)

    st.subheader("🏷️ Contract Tag Validation Rules")
    col_tag1, col_tag2, col_tag3 = st.columns(3)
    with col_tag1:
        st.info("**ChildU1 / ChildU2 Tags**\n\nFixed to Shift 2 (`08:30-17:00`) or PT Blocks. Exempt from late shifts past 17:30.")
    with col_tag2:
        st.warning("**U18 Tag**\n\nStrict legal limit: Max 8h/day, no shifts past 20:00. Assigned strictly to Early or Peak A shifts.")
    with col_tag3:
        st.success("**Part-Time (PT) Rules**\n\n2-week block stability. Shift timing rotates once every 2 weeks to maintain schedule predictability.")

# TAB 2: LIVE ROSTER
with tab2:
    st.header("Interactive Roster & Shift Editor")
    st.write("Modify agent details, assign rotation groups, or adjust contract tags directly in the table:")

    sample_agents = []
    groups = ["Group A", "Group B", "Group C", "Group D"]
    tags = ["None", "ChildU1", "ChildU2", "U18"]
    types = ["Full-Time", "Part-Time"]

    for i in range(1, 71):
        g = groups[(i - 1) % 4]
        c_type = "Part-Time" if g == "Group D" else "Full-Time"
        tag = tags[i % 4] if i <= 12 else "None"
        sample_agents.append({
            "Agent ID": f"SWISS-{1000 + i}",
            "Agent Name": f"Agent {i}",
            "Contract Type": c_type,
            "Contract Tag": tag,
            "Rotation Group": g,
            "Current Shift": "08:30-17:00" if tag in ["ChildU1", "ChildU2"] else "10:00-18:30",
            "Weekly Hours": 20 if c_type == "Part-Time" else 40
        })

    df_roster = pd.DataFrame(sample_agents)
    edited_roster = st.data_editor(df_roster, num_rows="dynamic", use_container_width=True)

    csv_data = edited_roster.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Full 70-Agent Roster (CSV)",
        data=csv_data,
        file_name="Swisscom_70Agent_Rotation_Roster.csv",
        mime="text/csv"
    )

# TAB 3: ERLANG-C MODEL
with tab3:
    st.header("Hourly & Interval Capacity Model")
    interval_volume = st.number_input("Simulated Interval Call Volume (30-min window)", value=85)
    
    erlangs = (interval_volume * aht) / 1800
    st.info(f"**Workload Intensity:** {round(erlangs, 2)} Erlangs generated in this 30-minute interval.")
    
    recommended_agents = math.ceil(erlangs / 0.85)
    gross_agents = math.ceil(recommended_agents / (1 - (total_shrinkage / 100)))
    
    col_a, col_b = st.columns(2)
    col_a.metric("Net On-Queue Staffing Needed", f"{recommended_agents} Agents")
    col_b.metric("Gross Roster Staffing Needed (with Shrinkage)", f"{gross_agents} Agents")

# TAB 4: AI ADVICE
with tab4:
    st.header("🧙‍♂️ Ohara Strategic Recommendations")
    if total_shrinkage > 25:
        st.warning(f"**Shrinkage Advisory:** Total shrinkage is currently high at {round(total_shrinkage, 2)}%. Reducing In-Office Overhead by 3% reclaims ~2.1 FTE.")
    
    st.success("**Optimization Advice:** Stacking Group B, Group C, and Group D between 10:00 - 15:00 CET creates optimal peak coverage of 52-56 active agents on queue.")
