import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Ohara WFM - Swisscom Engine", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom Strategic WFM Engine")
st.markdown("Dynamic Calendar Matrix, Multi-Metric Controls & Strategic Shift Rotation")

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
# CALENDAR MATRIX COMPUTATION
# ---------------------------------------------------------
intervals = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)]

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

days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
month_total_weight = sum([daily_curves[days_of_week[(d - 1) % 7]].sum() for d in range(1, total_month_days + 1)])

# Data Dictionaries for Matrix
dict_mins = {interval: {} for interval in intervals}
dict_calls = {interval: {} for interval in intervals}
dict_net = {interval: {} for interval in intervals}
dict_gross = {interval: {} for interval in intervals}

for d in range(1, total_month_days + 1):
    day_name = days_of_week[(d - 1) % 7]
    col_label = f"Day {d} ({day_name[:3]})"
    curve = daily_curves[day_name]
    
    day_weight_factor = 1.2 if day_name == "Monday" else (0.5 if day_name == "Saturday" else (0.3 if day_name == "Sunday" else 1.0))
    daily_mins = (call_volume / month_total_weight) * day_weight_factor
    
    for idx, interval in enumerate(intervals):
        int_mins = daily_mins * curve[idx]
        int_calls = int_mins / (aht / 60)
        erlang_val = (int_calls * aht) / 1800
        net_fte = math.ceil(erlang_val / 0.85) if erlang_val > 0 else 0
        gross_fte = math.ceil(net_fte / (1 - (total_shrinkage / 100))) if net_fte > 0 else 0
        
        dict_mins[interval][col_label] = round(int_mins, 1)
        dict_calls[interval][col_label] = round(int_calls, 1)
        dict_net[interval][col_label] = net_fte
        dict_gross[interval][col_label] = gross_fte

df_matrix_mins = pd.DataFrame(dict_mins).T
df_matrix_calls = pd.DataFrame(dict_calls).T
df_matrix_net = pd.DataFrame(dict_net).T
df_matrix_gross = pd.DataFrame(dict_gross).T

# ---------------------------------------------------------
# TAB NAVIGATION
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🧮 Monthly Distribution Matrix",
    "📈 Forecast vs. Capacity Chart",
    "📋 Verfügbarkeitsliste & Priority Auto-Mapping",
    "🔄 Dynamic Shift Rotation (Mon-Sun)"
])

# ---------------------------------------------------------
# TAB 1: MATRIX WITH METRIC TOGGLE
# ---------------------------------------------------------
with tab1:
    st.header(f"🧮 Monthly Calendar Matrix — {selected_month} ({total_month_days} Days)")
    st.write("Vertical: 30-minute operational intervals (07:00 – 22:00) | Horizontal: Calendar days across the month")
    
    metric_choice = st.radio(
        "Select Display Metric:",
        ["Workload Minutes (Min)", "Call Volume (Calls)", "Net Required FTE", "Gross Required FTE (with Shrinkage)"],
        horizontal=True
    )
    
    if metric_choice == "Workload Minutes (Min)":
        st.dataframe(df_matrix_mins, use_container_width=True)
    elif metric_choice == "Call Volume (Calls)":
        st.dataframe(df_matrix_calls, use_container_width=True)
    elif metric_choice == "Net Required FTE":
        st.dataframe(df_matrix_net, use_container_width=True)
    else:
        st.dataframe(df_matrix_gross, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: CHART
# ---------------------------------------------------------
with tab2:
    st.header(f"📈 Daily Interval Workload Chart — {selected_month}")
    selected_chart_day_idx = st.slider("Select Day of Month to Plot:", 1, total_month_days, 1)
    day_name_plot = days_of_week[(selected_chart_day_idx - 1) % 7]
    col_key = f"Day {selected_chart_day_idx} ({day_name_plot[:3]})"
    
    df_chart_plot = pd.DataFrame({
        "Gross Required FTE": df_matrix_gross[col_key],
        "Net On-Queue FTE Target": df_matrix_net[col_key]
    }, index=intervals)
    
    st.line_chart(df_chart_plot)

# ---------------------------------------------------------
# TAB 3: VERFÜGBARKEITSLISTE
# ---------------------------------------------------------
with tab3:
    st.header("📋 Verfügbarkeitsliste & Priority Constraint Auto-Mapping")
    if verfuegbarkeit_file is not None:
        try:
            if verfuegbarkeit_file.name.endswith(".csv"):
                df_agents = pd.read_csv(verfuegbarkeit_file)
            else:
                df_agents = pd.read_excel(verfuegbarkeit_file)
            st.success("Loaded Verfügbarkeitsliste!")
            st.dataframe(df_agents, use_container_width=True)
        except Exception as e:
            st.error(f"Error parsing file: {e}")
    else:
        st.info("💡 Upload `Verfügbarkeitsliste.xlsx` in the sidebar to auto-populate exact agent names.")

# ---------------------------------------------------------
# TAB 4: ROTATION
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
    
    for day in days_of_week:
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
