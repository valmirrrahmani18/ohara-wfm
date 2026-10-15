import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Ohara WFM - Swisscom Engine", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom Strategic WFM Engine")
st.markdown("Full Monthly Calendar Interval Distribution & Dynamic Multi-Week Rotation")

# ---------------------------------------------------------
# SIDEBAR PARAMETERS & FILE UPLOADERS
# ---------------------------------------------------------
st.sidebar.header("📅 Planning Period")
selected_month = st.sidebar.selectbox("Select Planning Month", [
    "January", "February", "March", "April", "May", "June", 
    "July", "August", "September", "October", "November", "December"
])

month_days_map = {
    "January": 31, "February": 28, "March": 31, "April": 30, "May": 31, "June": 30,
    "July": 31, "August": 31, "September": 30, "October": 31, "November": 30, "December": 31
}
total_month_days = month_days_map[selected_month]

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

# Executive Metrics Calculation
total_calls_forecast = call_volume / (aht / 60)
raw_workload_hours = call_volume / 60
gross_workload_hours = raw_workload_hours / (1 - (total_shrinkage / 100))
required_fte = round(gross_workload_hours / 168, 2)

st.subheader(f"📊 Executive Overview — {selected_month} ({total_month_days} Days)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Monthly Calls", f"{int(total_calls_forecast):,}")
col2.metric("Required Capacity", f"{required_fte} FTE")
col3.metric("Target SL", f"{target_sl}% in {target_time}s")
col4.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

st.markdown("---")

# ---------------------------------------------------------
# DAY-BY-DAY INTERVAL CURVES SETUP (07:00 - 22:00 CET)
# ---------------------------------------------------------
intervals = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)]

# Default day profile curves (Weekdays vs Weekends)
weekday_base = np.array([
    0.01, 0.02, 0.035, 0.05, 0.07, 0.085, 0.095, 0.10, 0.095, 0.09, 
    0.085, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 
    0.035, 0.03, 0.025, 0.02, 0.015, 0.01, 0.008, 0.005, 0.002, 0.001
])

weekend_base = np.array([
    0.005, 0.01, 0.02, 0.03, 0.05, 0.07, 0.08, 0.09, 0.085, 0.08, 
    0.075, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.015, 0.01, 0.008, 
    0.005, 0.003, 0.002, 0.001, 0.001, 0.0, 0.0, 0.0, 0.0, 0.0
])

daily_curves = {
    "Monday": (weekday_base * 1.15) / (weekday_base * 1.15).sum(),
    "Tuesday": weekday_base / weekday_base.sum(),
    "Wednesday": weekday_base / weekday_base.sum(),
    "Thursday": weekday_base / weekday_base.sum(),
    "Friday": (weekday_base * 0.95) / (weekday_base * 0.95).sum(),
    "Saturday": weekend_base / weekend_base.sum(),
    "Sunday": (weekend_base * 0.6) / (weekend_base * 0.6).sum()
}

# Parse uploaded file if provided
if verteilung_file is not None:
    try:
        if verteilung_file.name.endswith(".csv"):
            df_hist = pd.read_csv(verteilung_file)
        else:
            df_hist = pd.read_excel(verteilung_file)
        df_hist.columns = [str(c).strip().lower() for c in df_hist.columns]
        st.sidebar.success("Loaded Call Verteilung file!")
    except Exception as e:
        st.sidebar.error(f"Error reading file: {e}")

# Build Full Month Calendar Grid
days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Calculate monthly total weights to scale daily volume accurately
month_total_weight = sum([daily_curves[days_of_week[(d - 1) % 7]].sum() for d in range(1, total_month_days + 1)])

# Build Master DataFrame for the entire month
month_records = []
for d in range(1, total_month_days + 1):
    day_name = days_of_week[(d - 1) % 7]
    curve = daily_curves[day_name]
    
    # Scale daily volume based on weekday vs weekend demand profile
    day_weight_factor = 1.2 if day_name == "Monday" else (0.5 if day_name == "Saturday" else (0.3 if day_name == "Sunday" else 1.0))
    daily_mins = (call_volume / month_total_weight) * day_weight_factor
    
    for idx, interval in enumerate(intervals):
        int_mins = daily_mins * curve[idx]
        int_calls = int_mins / (aht / 60)
        erlang_val = (int_calls * aht) / 1800
        net_fte = math.ceil(erlang_val / 0.85) if erlang_val > 0 else 0
        gross_fte = math.ceil(net_fte / (1 - (total_shrinkage / 100))) if net_fte > 0 else 0
        
        month_records.append({
            "Day of Month": f"{selected_month} {d}",
            "Weekday": day_name,
            "Interval": interval,
            "Workload Minutes": round(int_mins, 1),
            "Distributed Calls": round(int_calls, 1),
            "Erlangs": round(erlang_val, 2),
            "Net Required FTE": net_fte,
            "Gross Required FTE": gross_fte
        })

df_full_month = pd.DataFrame(month_records)

# ---------------------------------------------------------
# TAB NAVIGATION
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🧮 Full Month Interval Workload Table",
    "📈 Daily Forecast vs. Capacity Chart",
    "📋 Verfügbarkeitsliste & Priority Auto-Mapping",
    "🔄 Dynamic Shift Rotation (Mon-Sun)"
])

# ---------------------------------------------------------
# TAB 1: FULL MONTH TABLE
# ---------------------------------------------------------
with tab1:
    st.header(f"🧮 Complete Monthly Interval Distribution — {selected_month}")
    st.write(f"Showing interval distribution for all **{total_month_days} calendar days** with distinct weekday/weekend profiles:")
    
    # Filter by specific calendar day if desired
    filter_day = st.selectbox("Filter View by Day of Month:", ["All Month"] + [f"{selected_month} {d}" for d in range(1, total_month_days + 1)])
    
    if filter_day != "All Month":
        df_display = df_full_month[df_full_month["Day of Month"] == filter_day]
