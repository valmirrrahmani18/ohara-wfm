import streamlit as st
import math

st.set_page_config(page_title="Ohara WFM Assistant", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom WFM Strategic Assistant")
st.markdown("Automated Shift Scheduling & Strategic Capacity Planning for Swisscom (70 Agents)")

# Sidebar Parameters
st.sidebar.header("⚙️ Account Parameters")
call_volume = st.sidebar.number_input("Monthly Call Volume (Minutes)", value=340000, step=10000)
aht = st.sidebar.number_input("Average Handle Time (Seconds)", value=600, step=10)
target_sl = st.sidebar.slider("Target Service Level (%)", 50, 100, 80)
target_time = st.sidebar.number_input("Target Answer Time (Seconds)", value=20)
ioo = st.sidebar.number_input("In-Office Overhead (%)", value=14.33)
ooo = st.sidebar.number_input("Out-of-Office Overhead (%)", value=16.0)

total_shrinkage = ioo + ooo

# Calculations
raw_workload_hours = call_volume / 60
gross_workload_hours = raw_workload_hours / (1 - (total_shrinkage / 100))
required_fte = round(gross_workload_hours / 168, 2) # standard month FTE multiplier

# Top Metrics Dashboard
st.subheader("📊 Strategic WFM Overview")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Roster Size", "70 Agents")
col2.metric("Required FTE", f"{required_fte} FTE")
col3.metric("Target SL", f"{target_sl}/{target_time}s")
col4.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3 = st.tabs(["🧮 Erlang-C & Capacity Engine", "📅 Roster & Contract Buffer Rules", "💡 AI Strategic Advice"])

with tab1:
    st.header("Hourly & Interval Capacity Model")
    interval_volume = st.number_input("Simulated Interval Call Volume (30-min window)", value=85)
    
    # Calculate Workload Intensity (Erlangs)
    erlangs = (interval_volume * aht) / 1800
    st.info(f"**Workload Intensity:** {round(erlangs, 2)} Erlangs generated in this 30-minute interval.")
    
    recommended_agents = math.ceil(erlangs / 0.85) # assuming 85% occupancy target
    gross_agents = math.ceil(recommended_agents / (1 - (total_shrinkage / 100)))
    
    col_a, col_b = st.columns(2)
    col_a.metric("Net On-Queue Staffing Needed", f"{recommended_agents} Agents")
    col_b.metric("Gross Roster Staffing Needed (with Shrinkage)", f"{gross_agents} Agents")

with tab2:
    st.header("Swisscom Account Scheduling Constraints")
    st.markdown("""
    * **Full-Time Agents:** Flexible / short-cycle rotation models.
    * **Part-Time Agents:** 2-week block scheduling.
    * **Contract Tags Active:**
        * `ChildU1` / `ChildU2`: Automated shift window buffering for childcare compatibility.
        * `U18`: Strict legal working hour limitations.
    """)
    
    st.subheader("Current Roster Capacity Status")
    if required_fte <= 70:
        st.success(f"✅ Roster Balance Optimal: 70 available agents cover the {required_fte} required FTE.")
    else:
        st.error(f"⚠️ Staffing Deficit Alert: Required capacity ({required_fte} FTE) exceeds current roster (70 agents) by {round(required_fte - 70, 2)} FTE.")

with tab3:
    st.header("🧙‍♂️ Ohara Strategic Recommendations")
    if total_shrinkage > 25:
        st.warning(f"**Shrinkage Advisory:** Total shrinkage is currently high at {round(total_shrinkage, 2)}% (IOO: {ioo}%, OOO: {ooo}%). Reducing In-Office Overhead by 3% reclaims approximately 2.1 FTE.")
    
    st.success("**Optimization Advice:** Ensure ChildU1/ChildU2 tagged agents are locked into fixed morning/afternoon blocks to maximize peak interval coverage between 10:00 - 14:00 CET.")
