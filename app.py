import streamlit as st
import pandas as pd
import numpy as np
import datetime
import math

st.set_page_config(page_title="Ohara WFM - Swisscom Engine", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom Strategic WFM Engine")
st.markdown("Dynamic Calendar Matrix, Multi-Metric Controls & Strategic Shift Rotation")

# ---------------------------------------------------------
# SIDEBAR PARAMETERS & FILE UPLOADERS
# ---------------------------------------------------------
st.sidebar.header("📅 Planning Period")
selected_month_name = st.sidebar.selectbox("Select Planning Month", [
    "January", "February", "March", "April", "May", "June", 
    "July", "August", "September", "October", "November", "December"
], index=11) # Default to December

month_num_map = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
}

month_num = month_num_map[selected_month_name]
year = 2026

if month_num in [1, 3, 5, 7, 8, 10, 12]:
    total_month_days = 31
elif month_num in [4, 6, 9, 11]:
    total_month_days = 30
else:
    total_month_days = 28

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

st.subheader(f"📊 Executive Overview — {selected_month_name} {year} ({total_month_days} Days)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Monthly Calls", f"{int(total_calls_forecast):,}")
col2.metric("Required Capacity", f"{required_fte} FTE")
col3.metric("Target SL", f"{target_sl}% in {target_time}s")
col4.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

st.markdown("---")

# ---------------------------------------------------------
# SMART TIME-BUCKETING FILE PARSING (07:00 - 22:00 CET)
# ---------------------------------------------------------
intervals = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)]
days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

base_curves_default = {
    "Monday": np.array([0.01, 0.02, 0.035, 0.05, 0.07, 0.09, 0.10, 0.11, 0.10, 0.09, 0.08, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 0.035, 0.03, 0.025, 0.02, 0.015, 0.012, 0.01, 0.008, 0.006, 0.004, 0.002, 0.001]),
    "Tuesday": np.array([0.012, 0.022, 0.04, 0.055, 0.075, 0.085, 0.09, 0.095, 0.09, 0.085, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 0.035, 0.03, 0.025, 0.02, 0.015, 0.012, 0.01, 0.007, 0.005, 0.003, 0.001]),
    "Wednesday": np.array([0.015, 0.025, 0.038, 0.052, 0.072, 0.088, 0.092, 0.098, 0.092, 0.088, 0.082, 0.078, 0.072, 0.068, 0.062, 0.058, 0.052, 0.048, 0.042, 0.038, 0.032, 0.028, 0.022, 0.018, 0.014, 0.01, 0.008, 0.005, 0.003, 0.001]),
    "Thursday": np.array([0.011, 0.021, 0.037, 0.049, 0.069, 0.083, 0.093, 0.102, 0.094, 0.089, 0.083, 0.079, 0.073, 0.069, 0.063, 0.059, 0.053, 0.049, 0.043, 0.039, 0.033, 0.029, 0.023, 0.019, 0.015, 0.011, 0.008, 0.005, 0.003, 0.001]),
    "Friday": np.array([0.013, 0.023, 0.041, 0.053, 0.073, 0.081, 0.088, 0.094, 0.088, 0.084, 0.079, 0.075, 0.071, 0.067, 0.063, 0.059, 0.055, 0.05, 0.045, 0.04, 0.035, 0.03, 0.025, 0.02, 0.016, 0.012, 0.009, 0.006, 0.003, 0.001]),
    "Saturday": np.array([0.008, 0.015, 0.025, 0.035, 0.05, 0.065, 0.075, 0.085, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 0.035, 0.03, 0.025, 0.02, 0.016, 0.012, 0.009, 0.007, 0.005, 0.003, 0.002, 0.001, 0.001]),
    "Sunday": np.array([0.005, 0.01, 0.018, 0.028, 0.04, 0.055, 0.065, 0.075, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045, 0.04, 0.035, 0.03, 0.025, 0.02, 0.016, 0.012, 0.009, 0.007, 0.005, 0.003, 0.002, 0.001, 0.001, 0.001, 0.001])
}

daily_curves = {}
file_parsed = False

if verteilung_file is not None:
    try:
        if verteilung_file.name.endswith(".csv"):
            df_hist = pd.read_csv(verteilung_file)
        else:
            df_hist = pd.read_excel(verteilung_file)
        
        col_map = {str(c).strip().lower(): c for c in df_hist.columns}
        
        time_col = next((col_map[c] for c in col_map if 'intervall' in c or 'time' in c or 'start' in c), None)
        day_col = next((col_map[c] for c in col_map if 'day' in c or 'woche' in c or 'tag' in c), None)
        vq_col = next((col_map[c] for c in col_map if 'vq' in c or 'entered' in c or 'volume' in c or 'calls' in c), None)
        
        if time_col and day_col and vq_col:
            day_translation = {
                'monday': 'Monday', 'montag': 'Monday', 'mon': 'Monday', '1': 'Monday',
                'tuesday': 'Tuesday', 'dienstag': 'Tuesday', 'tue': 'Tuesday', '2': 'Tuesday',
                'wednesday': 'Wednesday', 'mittwoch': 'Wednesday', 'wed': 'Wednesday', '3': 'Wednesday',
                'thursday': 'Thursday', 'donnerstag': 'Thursday', 'thu': 'Thursday', '4': 'Thursday',
                'friday': 'Friday', 'freitag': 'Friday', 'fri': 'Friday', '5': 'Friday',
                'saturday': 'Saturday', 'samstag': 'Saturday', 'sat': 'Saturday', '6': 'Saturday',
                'sunday': 'Sunday', 'sonntag': 'Sunday', 'sun': 'Sunday', '7': 'Sunday'
            }
            
            df_hist['standard_day'] = df_hist[day_col].astype(str).str.strip().str.lower().map(day_translation)
            
            # Helper function to convert time strings (like 07:15, 07:45) into standard 30-min interval buckets (07:00, 07:30)
            def time_to_bucket(t_val):
                try:
                    t_str = str(t_val).strip()
                    parts = t_str.split(':')
                    h = int(parts[0])
                    m = int(parts[1]) if len(parts) > 1 else 0
                    total_mins = h * 60 + m
                    bucket_mins = (total_mins // 30) * 30
                    bh = bucket_mins // 60
                    bm = bucket_mins % 60
                    return f"{bh:02d}:{bm:02d}"
                except:
                    return None

            df_hist['bucket_interval'] = df_hist[time_col].apply(time_to_bucket)
            df_hist['numeric_vq'] = pd.to_numeric(df_hist[vq_col], errors='coerce').fillna(0)
            
            for std_day in days_list:
                sub_df = df_hist[df_hist['standard_day'] == std_day]
                if not sub_df.empty:
                    # Aggregate 15-min or granular intervals into 30-min buckets using sum()
                    grouped = sub_df.groupby('bucket_interval')['numeric_vq'].sum().to_dict()
                    
                    curve_vals = []
                    for interval in intervals:
                        curve_vals.append(grouped.get(interval, 0.0))
                    
                    arr = np.array(curve_vals)
                    if arr.sum() > 0:
                        daily_curves[std_day] = arr / arr.sum()
                    else:
                        daily_curves[std_day] = base_curves_default[std_day] / base_curves_default[std_day].sum()
                else:
                    daily_curves[std_day] = base_curves_default[std_day] / base_curves_default[std_day].sum()
            file_parsed = True
            st.sidebar.success("Successfully parsed & bucketeled intervals (e.g. 07:15 -> 07:00)! 🤗")
        else:
            st.sidebar.warning("Required columns not found. Using default curves.")
    except Exception as e:
        st.sidebar.error(f"Error reading file: {e}")

if not file_parsed:
    for day in days_list:
        daily_curves[day] = base_curves_default[day] / base_curves_default[day].sum()

weekday_abbr_map = {0: "Mo", 1: "Tu", 2: "We", 3: "Th", 4: "Fr", 5: "Sa", 6: "Su"}
weekday_full_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}

month_total_weight = 0
for day_num in range(1, total_month_days + 1):
    dt = datetime.date(year, month_num, day_num)
    day_full = weekday_full_map[dt.weekday()]
    day_factor = 1.2 if day_full == "Monday" else (0.7 if day_full in ["Saturday", "Sunday"] else 1.0)
    month_total_weight += day_factor

dict_mins = {interval: {} for interval in intervals}
dict_calls = {interval: {} for interval in intervals}
dict_net = {interval: {} for interval in intervals}
dict_gross = {interval: {} for interval in intervals}

for day_num in range(1, total_month_days + 1):
    dt = datetime.date(year, month_num, day_num)
    date_str = f"{day_num:02d}"
    day_abbr = weekday_abbr_map[dt.weekday()]
    day_full = weekday_full_map[dt.weekday()]
    
    col_tuple = (date_str, day_abbr)
    curve = daily_curves[day_full]
    
    day_factor = 1.2 if day_full == "Monday" else (0.7 if day_full in ["Saturday", "Sunday"] else 1.0)
    daily_mins = (call_volume / month_total_weight) * day_factor
    
    for idx, interval in enumerate(intervals):
        int_mins = daily_mins * curve[idx]
        int_calls = int_mins / (aht / 60)
        erlang_val = (int_calls * aht) / 1800
        net_fte = math.ceil(erlang_val / 0.85) if erlang_val > 0 else 0
        gross_fte = math.ceil(net_fte / (1 - (total_shrinkage / 100))) if net_fte > 0 else 0
        
        dict_mins[interval][col_tuple] = round(int_mins, 1)
        dict_calls[interval][col_tuple] = round(int_calls, 1)
        dict_net[interval][col_tuple] = net_fte
        dict_gross[interval][col_tuple] = gross_fte

df_matrix_mins = pd.DataFrame(dict_mins).T
df_matrix_calls = pd.DataFrame(dict_calls).T
df_matrix_net = pd.DataFrame(dict_net).T
df_matrix_gross = pd.DataFrame(dict_gross).T

columns_multiindex = pd.MultiIndex.from_tuples(df_matrix_mins.columns, names=["Date", "Day"])
df_matrix_mins.columns = columns_multiindex
df_matrix_calls.columns = columns_multiindex
df_matrix_net.columns = columns_multiindex
df_matrix_gross.columns = columns_multiindex

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
# TAB 1: MATRIX
# ---------------------------------------------------------
with tab1:
    st.header(f"🧮 Monthly Calendar Matrix — {selected_month_name} {year}")
    st.write("Vertical: 30-minute intervals (07:00 – 22:00) | Row 1: Calendar Date | Row 2: Weekday Abbreviation")
    
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
    st.header(f"📈 Daily Interval Workload Chart — {selected_month_name} {year}")
    selected_chart_day_num = st.slider("Select Day of Month to Plot:", 1, total_month_days, 1)
    
    dt_chart = datetime.date(year, month_num, selected_chart_day_num)
    col_tuple_chart = (f"{selected_chart_day_num:02d}", weekday_abbr_map[dt_chart.weekday()])
    
    df_chart_plot = pd.DataFrame({
        "Gross Required FTE": df_matrix_gross[col_tuple_chart],
        "Net On-Queue FTE Target": df_matrix_net[col_tuple_chart]
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
    
    days_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
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
    
    for day in days_full:
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
