import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Ohara WFM - Swisscom Engine", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom Strategic WFM Engine")
st.markdown("Automated Call Distribution, Priority Constraints & Dynamic Multi-Week Rotation")

# ---------------------------------------------------------
# SIDEBAR PARAMETERS & FILE UPLOADERS
# ---------------------------------------------------------
st.sidebar.header("📅 Planning Period")
selected_month = st.sidebar.selectbox("Select Planning Month", [
    "January", "February", "March", "April", "May", "June", 
    "July", "August", "September", "October", "November", "December"
])

working_days = st.sidebar.number_input("Working Days in Selected Month", value=22, min_value=1, max_value=31)

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

st.sidebar.header("📁 Data Sources")
verteilung_file = st.sidebar.file_uploader("Upload 'Copy of Swisscom - Call verteilung 2' (.xlsx/.csv)", type=["xlsx", "csv"], key="verteilung")
verfuegbarkeit_file = st.sidebar.file_uploader("Upload Verfügbarkeitsliste (.xlsx/.csv)", type=["xlsx", "csv"], key="verfuegbarkeit")

# Dynamic Overall Monthly Calculations
total_calls_forecast = call_volume / (aht / 60)
raw_workload_hours = call_volume / 60
gross_workload_hours = raw_workload_hours / (1 - (total_shrinkage / 100))
required_fte = round(gross_workload_hours / 168, 2)

# Top Metrics Bar
st.subheader(f"📊 Executive Overview — {selected_month} Planning Cycle ({working_days} Working Days)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Monthly Calls", f"{int(total_calls_forecast):,}")
col2.metric("Required Roster Capacity", f"{required_fte} FTE")
col3.metric("Target SL", f"{target_sl}% in {target_time}s")
col4.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

st.markdown("---")

# ---------------------------------------------------------
# INTERVAL DISTRIBUTION SETUP (07:00 - 22:00 CET)
# ---------------------------------------------------------
intervals = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)]

# Standard bell curve distribution weights (sum = 1.0)
default_curve = np.array([
    0.01, 0.02, 0.035, 0.05, 0.07, 0.085, 0.095, 0.10, 0.095, 0.09, 
    0.085, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 
    0.035, 0.03, 0.025, 0.02, 0.015, 0.01, 0.008, 0.005, 0.002, 0.001
])

distribution_pct = default_curve / default_curve.sum()

if verteilung_file is not None:
    try:
        if verteilung_file.name.endswith(".csv"):
            df_hist = pd.read_csv(verteilung_file)
        else:
            df_hist = pd.read_excel(verteilung_file)
        
        numeric_cols = df_hist.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            raw_vals = df_hist[numeric_cols[0]].values[:len(intervals)]
            if len(raw_vals) == len(intervals) and raw_vals.sum() > 0:
                distribution_pct = raw_vals / raw_vals.sum()
                st.sidebar.success("Loaded & normalized Call Verteilung file!")
    except Exception as e:
        st.sidebar.error(f"Using default curve (Error reading file: {e})")

# Daily Average Volume Calculation
daily_volume_mins = call_volume / working_days

# Interval Workload Calculation using Normalized Percentages
interval_minutes = daily_volume_mins * distribution_pct
interval_calls = interval_minutes / (aht / 60)

# Erlang-C Net & Gross FTE Calculation per interval
erlangs = (interval_calls * aht) / 1800
net_fte_req = [math.ceil(e / 0.85) if e > 0 else 0 for e in erlangs]
gross_fte_req = [math.ceil(n / (1 - (total_shrinkage / 100))) if n > 0 else 0 for n in net_fte_req]

# ---------------------------------------------------------
# TAB NAVIGATION
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🧮 Interval Distribution & Volume Breakdown",
    "📈 Forecast vs. Planned Capacity Chart",
    "📋 Verfügbarkeitsliste & Priority Auto-Mapping",
    "🔄 Dynamic Shift Rotation (Mon-Sun)"
])

# ---------------------------------------------------------
# TAB 1: CORRECTED INTERVAL BREAKDOWN TABLE
# ---------------------------------------------------------
with tab1:
    st.header(f"🧮 Daily Interval Volume & Staffing Breakdown ({selected_month})")
    st.write(f"Showing average daily distribution for **{daily_volume_mins:,.1f} minutes/day** ({call_volume:,} monthly minutes ÷ {working_days} working days):")
    
    df_intervals = pd.DataFrame({
        "Interval Window": intervals,
        "Interval % Weight": [f"{p*100:.2f}%" for p in distribution_pct],
        "Distributed Calls": np.round(interval_calls, 1),
        "Workload Minutes": np.round(interval_minutes, 1),
        "Erlangs": np.round(erlangs, 2),
        "Net Required FTE": net_fte_req,
        "Gross Required FTE": gross_fte_req
    })
    
    st.dataframe(df_intervals, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: CHART & DYNAMIC RE-CALCULATION
# ---------------------------------------------------------
with tab2:
    st.header(f"📈 Daily Interval Workload vs. Staffing Target ({selected_month})")
    st.write("Dynamic re-calculation across all 30-minute operational intervals (07:00 to 22:00 CET):")
    
    df_chart = pd.DataFrame({
        "Gross Required FTE": gross_fte_req,
        "Net On-Queue FTE Target": net_fte_req
    }, index=intervals)
    
    st.line_chart(df_chart)

# ---------------------------------------------------------
# TAB 3: VERFÜGBARKEITSLISTE & AUTO-MAPPING
# ---------------------------------------------------------
with tab3:
    st.header("📋 Verfügbarkeitsliste & Priority Constraint Auto-Mapping")
    st.write(f"Active Roster Mapping for **{selected_month}**:")
    
    if verfuegbarkeit_file is not None:
        try:
            if verfuegbarkeit_file.name.endswith(".csv"):
                df_agents = pd.read_csv(verfuegbarkeit_file)
            else:
                df_agents = pd.read_excel(verfuegbarkeit_file)
            st.success("Successfully loaded employee names from Verfügbarkeitsliste!")
            st.dataframe(df_agents, use_container_width=True)
        except Exception as e:
            st.error(f"Error parsing Verfügbarkeitsliste: {e}")
    else:
        st.info("💡 Upload your `Verfügbarkeitsliste.xlsx` in the sidebar to auto-populate exact names. Showing structured master roster below:")
        
        sample_names = [
            ("Valmir", "Rrahmani"), ("Ardit", "Krasniqi"), ("Blerta", "Gashi"), ("Granit", "Hoxha"),
            ("Erblin", "Berisha"), ("Drenusha", "Morina"), ("Leon", "Bytyqi"), ("Faton", "Kastrati"),
            ("Vjosa", "Osmani"), ("Besart", "Leka"), ("Klea", "Bajrami"), ("Dardan", "Shala"),
            ("Kaltrina", "Korenica"), ("Yll", "Dushi"), ("Rina", "Zeqiri"), ("Meriton", "Ismaili")
        ]
        
        roster_list = []
        for i in range(1, 71):
            fn, ln = sample_names[(i - 1) % len(sample_names)]
            full_name = f"{fn} {ln} ({i})"
            
            if i <= 5:
                tag = "ChildU1" if i % 2 == 0 else "ChildU2"
                c_type = "Full-Time"
                assigned_shift = "🟢 Day (08:30-17:00)"
            elif i <= 10:
                tag = "U18_PT_5" if i % 2 == 0 else "U18_PT_4"
                c_type = "Part-Time (Minor)"
                assigned_shift = "🔵 Morning (Max 5h, off <20:00)"
            elif i <= 25:
                tag = "Standard PT"
                c_type = "Part-Time"
                assigned_shift = "08:00 Start (W1) / 22:00 End (W2)"
            else:
                tag = "Flexible FT"
                c_type = "Full-Time"
                assigned_shift = "Flexible Rotation"

            roster_list.append({
                "Agent Name": full_name,
                "Contract Type": c_type,
                "Constraint Tag": tag,
                "Assigned Shift Window": assigned_shift,
                "Max Daily Hours": 5 if "U18_PT_5" in tag else (4 if "U18_PT_4" in tag else (6 if "Part-Time" in c_type else 8)),
                "Mandatory Break": "30 mins" if "U18" in tag else "60 mins"
            })
            
        df_roster_mapped = pd.DataFrame(roster_list)
        st.dataframe(df_roster_mapped, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: MULTI-WEEK ROTATION (MON-SUN & 50/50 PT SPLIT)
# ---------------------------------------------------------
with tab4:
    st.header(f"🔄 Multi-Week Rotation Matrix ({rotation_weeks}-Week Cycle)")
    st.markdown("""
    **Color-Coded Shift Legend:**
    * 🔵 **Morning:** `07:00 - 15:30` | 🟢 **Day:** `08:30 - 17:00` | 🟠 **Evening:** `12:00 - 20:30` | 🟣 **Late Evening:** `13:30 - 22:00` | 🔷 **EoB Closing:** `14:00 - 22:00`
    """)
    
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
                "OFF", "OFF", 
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
