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

st.sidebar.header("📁 Data Sources (Point 1 & 2)")
verteilung_file = st.sidebar.file_uploader("Upload Call Verteilung File (.xlsx/.csv)", type=["xlsx", "csv"], key="verteilung")
verfuegbarkeit_file = st.sidebar.file_uploader("Upload Verfügbarkeitsliste (.xlsx/.csv)", type=["xlsx", "csv"], key="verfuegbarkeit")

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
# INTERVAL DISTRIBUTION SETUP (Point 2)
# ---------------------------------------------------------
intervals = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)] + ["22:00"]

if verteilung_file is not None:
    try:
        if verteilung_file.name.endswith(".csv"):
            df_dist_raw = pd.read_csv(verteilung_file)
        else:
            df_dist_raw = pd.read_excel(verteilung_file)
        st.sidebar.success("Loaded Call Verteilung file!")
        # Map values if file structure exists, else fallback to curve
        if "Interval" in df_dist_raw.columns and "Volume" in df_dist_raw.columns:
            interval_calls = df_dist_raw["Volume"].values[:len(intervals)-1]
            interval_minutes = interval_calls * (aht / 60)
        else:
            base_curve = np.array([
                0.01, 0.02, 0.035, 0.05, 0.07, 0.085, 0.095, 0.10, 0.095, 0.09, 
                0.085, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 
                0.035, 0.03, 0.025, 0.02, 0.015, 0.01, 0.008, 0.005, 0.002, 0.001
            ])
            normalized_curve = base_curve / base_curve.sum()
            interval_minutes = call_volume * normalized_curve
            interval_calls = interval_minutes / (aht / 60)
    except Exception as e:
        st.sidebar.error(f"Error reading Call Verteilung: {e}")
        base_curve = np.array([
            0.01, 0.02, 0.035, 0.05, 0.07, 0.085, 0.095, 0.10, 0.095, 0.09, 
            0.085, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 
            0.035, 0.03, 0.025, 0.02, 0.015, 0.01, 0.008, 0.005, 0.002, 0.001
        ])
        normalized_curve = base_curve / base_curve.sum()
        interval_minutes = call_volume * normalized_curve
        interval_calls = interval_minutes / (aht / 60)
else:
    base_curve = np.array([
        0.01, 0.02, 0.035, 0.05, 0.07, 0.085, 0.095, 0.10, 0.095, 0.09, 
        0.085, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 
        0.035, 0.03, 0.025, 0.02, 0.015, 0.01, 0.008, 0.005, 0.002, 0.001
    ])
    normalized_curve = base_curve / base_curve.sum()
    interval_minutes = call_volume * normalized_curve
    interval_calls = interval_minutes / (aht / 60)

# Erlang-C Net & Gross FTE Calculation per interval
erlangs = (interval_calls * aht) / 1800
net_fte_req = [math.ceil(e / 0.85) if e > 0 else 0 for e in erlangs]
gross_fte_req = [math.ceil(n / (1 - (total_shrinkage / 100))) if n > 0 else 0 for n in net_fte_req]

# ---------------------------------------------------------
# TAB NAVIGATION
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Verfügbarkeitsliste & Priority Auto-Mapping",
    "📈 Forecast vs. Planned Capacity Chart",
    "🔄 Dynamic Shift Rotation (Mon-Sun)",
    "🧮 Interval Distribution (Swisscom 07:00-22:00)"
])

# ---------------------------------------------------------
# TAB 1: VERFÜGBARKEITSLISTE & AUTO-MAPPING (Point 1)
# ---------------------------------------------------------
with tab1:
    st.header("📋 Verfügbarkeitsliste & Priority Constraint Auto-Mapping")
    st.write("Below is the mapped roster with real agent names and priority constraint tags:")
    
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
# TAB 2: CHART & DYNAMIC RE-CALCULATION (Point 2)
# ---------------------------------------------------------
with tab2:
    st.header("📈 Interval Workload vs. Planned Staffing Capacity")
    st.write("Dynamic re-calculation across all 30-minute operational intervals (07:00 to 22:00 CET):")
    
    df_chart = pd.DataFrame({
        "Gross Required FTE": gross_fte_req,
        "Net On-Queue FTE Target": net_fte_req
    },
