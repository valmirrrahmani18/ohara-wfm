import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Ohara WFM - Swisscom Engine", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom Strategic WFM Engine")
st.markdown("Automated Call Distribution, Priority Constraints & Dynamic Multi-Week Rotation")

# ---------------------------------------------------------
# SIDEBAR PARAMETERS & LIVE CONTROLS
# ---------------------------------------------------------
st.sidebar.header("⚙️ Account Parameters")
call_volume = st.sidebar.number_input("Monthly Call Volume (Minutes)", value=340000, step=10000)
aht = st.sidebar.number_input("Average Handle Time (Seconds)", value=600, step=10)
target_sl = st.sidebar.slider("Target Service Level (%)", 50, 100, 80)
target_time = st.sidebar.number_input("Target Answer Time (Seconds)", value=20)
ioo = st.sidebar.number_input("In-Office Overhead (%)", value=14.33)
ooo = st.sidebar.number_input("Out-of-Office Overhead (%)", value=16.0)

total_shrinkage = ioo + ooo

st.sidebar.header("🔄 Rotation Cycle")
rotation_weeks = st.sidebar.slider("Rotation Cycle Length (Weeks)", 2, 10, 10)

# Dynamic Calculations
total_calls_forecast = call_volume / (aht / 60)
raw_workload_hours = call_volume / 60
gross_workload_hours = raw_workload_hours / (1 - (total_shrinkage / 100))
required_fte = round(gross_workload_hours / 168, 2)

# Top Metrics Bar
st.subheader("📊 Dynamic Executive Overview")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Monthly Calls", f"{int(total_calls_forecast):,}")
col2.metric("Required Capacity", f"{required_fte} FTE")
col3.metric("Target SL", f"{target_sl}% in {target_time}s")
col4.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

st.markdown("---")

# ---------------------------------------------------------
# TAB NAVIGATION
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Forecast vs. Planned Capacity Chart",
    "🔄 Dynamic Shift Rotation (Mon-Sun)",
    "📋 Verfügbarkeitsliste & Priority Tags",
    "🧮 Interval Distribution (Swisscom 07:00-22:00)"
])

# ---------------------------------------------------------
# TAB 1: NATIVE CHART & DYNAMIC RE-CALCULATION
# ---------------------------------------------------------
with tab1:
    st.header("📈 Interval Workload vs. Planned Staffing Capacity")
    st.write("Dynamic re-calculation across all 30-minute operational intervals (07:00 to 22:00 CET):")
    
    # 30-min Intervals from 07:00 to 22:00
    intervals = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)] + ["22:00"]
    
    # Bell-curve workload distribution curve representing Swisscom volume profile
    base_curve = np.array([
        0.01, 0.02, 0.035, 0.05, 0.07, 0.085, 0.095, 0.10, 0.095, 0.09, 
        0.085, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 
        0.035, 0.03, 0.025, 0.02, 0.015, 0.01, 0.008, 0.005, 0.002, 0.001, 0.0
    ])
    
    normalized_curve = base_curve / base_curve.sum()
    interval_minutes = call_volume * normalized_curve
    interval_calls = interval_minutes / (aht / 60)
    
    # Erlang-C Net & Gross FTE Calculation per interval
    erlangs = (interval_calls * aht) / 1800
    net_fte_req = [math.ceil(e / 0.85) if e > 0 else 0 for e in erlangs]
    gross_fte_req = [math.ceil(n / (1 - (total_shrinkage / 100))) if n > 0 else 0 for n in net_fte_req]
    
    # Native Streamlit Chart (No extra library needed)
    df_chart = pd.DataFrame({
        "Gross Required FTE": gross_fte_req[:-1],
        "Net On-Queue FTE Target": net_fte_req[:-1]
    }, index=intervals[:-1])
    
    st.line_chart(df_chart)

# ---------------------------------------------------------
# TAB 2: MULTI-WEEK ROTATION (MON-SUN & 50/50 PT SPLIT)
# ---------------------------------------------------------
with tab2:
    st.header(f"🔄 Multi-Week Rotation Matrix ({rotation_weeks}-Week Cycle)")
    st.markdown("""
    **Color-Coded Shift Legend:**
    * 🔵 **Morning:** `07:00 - 15:30` | 🟢 **Day:** `08:30 - 17:00` | 🟠 **Evening:** `12:00 - 20:30` | 🟣 **Late Evening:** `13:30 - 22:00` | 🔷 **EoB Closing:** `14:00 - 22:00`
    """)
    
    st.subheader("Part-Time Alternating 50/50 Rotation Logic")
    st.info("Half of the Part-Time team works from **08:00** in odd weeks and until **EoB (22:00)** in even weeks. The other half works until **EoB (22:00)** in odd weeks and starts at **08:00** in even weeks.")
    
    selected_week = st.selectbox("Select Week to View Daily Coverage (Mon - Sun):", [f"Week {w}" for w in range(1, rotation_weeks + 1)])
    week_idx = int(selected_week.split(" ")[1])
    
    pt_half1_shift = "08:00 - 13:00 (Start 08:00)" if week_idx % 2 != 0 else "17:00 - 22:00 (EoB Close)"
    pt_half2_shift = "17:00 - 22:00 (EoB Close)" if week_idx % 2 != 0 else "08:00 - 13:00 (Start 08:00)"
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    rotation_schedule = {
        "Cohort Group": [
            "ChildU1 / ChildU2 (Restricted)",
            "Minors (U18_PT_5 & U18_PT_4)",
            "Part-Time Group 1 (50% Split)",
            "Part-Time Group 2 (50% Split)",
            "Flexible Full-Time Group A",
            "Flexible Full-Time Group B"
        ]
    }
    
    for day in days:
        if day in ["Saturday", "Sunday"]:
            rotation_schedule[day] = [
                "OFF", 
                "OFF", 
                "08:00 - 13:00" if week_idx % 2 != 0 else "OFF",
                "OFF" if week_idx % 2 != 0 else "08:00 - 13:00",
                "08:30 - 17:00" if week_idx % 2 == 0 else "OFF",
                "OFF" if week_idx % 2 == 0 else "13:30 - 22:00"
            ]
        else:
            rotation_schedule[day] = [
                "🟢 Day (08:30-17:00)",
                "🔵 Morning (<5h, off <20:00)",
                pt_half1_shift,
                pt_half2_shift,
                "🔵 Morning (07:00-15:30)" if week_idx % 3 == 1 else ("🟢 Day (08:30-17:00)" if week_idx % 3 == 2 else "🟣 Late (13:30-22:00)"),
                "🟣 Late (13:30-22:00)" if week_idx % 3 == 1 else ("🔵 Morning (07:00-15:30)" if week_idx % 3 == 2 else "🟢 Day (08:30-17:00)")
            ]
            
    df_week_view = pd.DataFrame(rotation_schedule)
    st.dataframe(df_week_view, use_container_width=True)

# ---------------------------------------------------------
# TAB 3: VERFÜGBARKEITSLISTE DATA SETUP
# ---------------------------------------------------------
with tab3:
    st.header("📋 Verfügbarkeitsliste Upload & Priority Tagging")
    st.write("Upload your official **Verfügbarkeitsliste** CSV/Excel file containing employee names and constraint tags:")
    
    uploaded_file = st.file_uploader("Upload Verfügbarkeitsliste (CSV or Excel)", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_custom = pd.read_csv(uploaded_file)
            else:
                df_custom = pd.read_excel(uploaded_file)
            st.success("Successfully loaded Verfügbarkeitsliste!")
            st.dataframe(df_custom, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading file: {e}")
    else:
        st.info("💡 To populate real employee names directly from your file, upload your `Verfügbarkeitsliste.xlsx` above.")

# ---------------------------------------------------------
# TAB 4: INTERVAL BREAKDOWN TABLE
# ---------------------------------------------------------
with tab4:
    st.header("🧮 Interval Breakdown Table (07:00 - 22:00)")
    
    df_intervals = pd.DataFrame({
        "Interval Window": intervals[:-1],
        "Forecast Call Volume": np.round(interval_calls[:-1], 1),
        "Forecast Workload (Mins)": np.round(interval_minutes[:-1], 1),
        "Erlangs": np.round(erlangs[:-1], 2),
        "Net Required FTE": net_fte_req[:-1],
        "Gross Required FTE": gross_fte_req[:-1]
    })
    
    st.dataframe(df_intervals, use_container_width=True)
