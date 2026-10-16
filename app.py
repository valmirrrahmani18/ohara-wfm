import streamlit as st
import pandas as pd
import numpy as np
import datetime
import math

st.set_page_config(page_title="Ohara WFM - Swisscom Engine", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom Strategic WFM Engine")
st.markdown("Dynamic Calendar Matrix, Multi-Metric Controls, Shift Rotation & NICE/WFM CSV Export")

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

st.sidebar.header("⚙️ Account Parameters")
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

st.markdown("---")

# ---------------------------------------------------------
# EXTENDED CALENDAR RANGE (1st of Month to Final Sunday)
# ---------------------------------------------------------
start_date = datetime.date(year, month_num, 1)

if month_num in [1, 3, 5, 7, 8, 10, 12]:
    last_day_num = 31
elif month_num in [4, 6, 9, 11]:
    last_day_num = 30
else:
    last_day_num = 28

end_of_month_date = datetime.date(year, month_num, last_day_num)
days_to_sunday = (6 - end_of_month_date.weekday()) % 7
end_date = end_of_month_date + datetime.timedelta(days=days_to_sunday)

date_list = []
curr = start_date
while curr <= end_date:
    date_list.append(curr)
    curr += datetime.timedelta(days=1)

# ---------------------------------------------------------
# DIRECT ABSOLUTE VQ ENTERED PARSER (07:00 - 22:00 CET)
# ---------------------------------------------------------
intervals = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)]
days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Realistic default absolute curves if no file is uploaded
default_day_profile = {
    "Monday": {i: 40.0 for i in intervals},
    "Tuesday": {i: 40.0 for i in intervals},
    "Wednesday": {i: 40.0 for i in intervals},
    "Thursday": {i: 40.0 for i in intervals},
    "Friday": {i: 40.0 for i in intervals},
    "Saturday": {i: 20.0 for i in intervals},
    "Sunday": {i: 15.0 for i in intervals}
}

daily_absolute_curves = {}
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
        vq_col = next((col_map[c] for c in col_map if 'vq' in c or 'entered' in c), None)
        
        if time_col and day_col and vq_col:
            day_translation = {
                'monday': 'Monday', 'montag': 'Monday', 'mon': 'Monday', 'mo': 'Monday', '1': 'Monday', '1.0': 'Monday',
                'tuesday': 'Tuesday', 'dienstag': 'Tuesday', 'tue': 'Tuesday', 'di': 'Tuesday', '2': 'Tuesday', '2.0': 'Tuesday',
                'wednesday': 'Wednesday', 'mittwoch': 'Wednesday', 'wed': 'Wednesday', 'mi': 'Wednesday', '3': 'Wednesday', '3.0': 'Wednesday',
                'thursday': 'Thursday', 'donnerstag': 'Thursday', 'thu': 'Thursday', 'do': 'Thursday', '4': 'Thursday', '4.0': 'Thursday',
                'friday': 'Friday', 'freitag': 'Friday', 'fri': 'Friday', 'fr': 'Friday', '5': 'Friday', '5.0': 'Friday',
                'saturday': 'Saturday', 'samstag': 'Saturday', 'sat': 'Saturday', 'sa': 'Saturday', '6': 'Saturday', '6.0': 'Saturday',
                'sunday': 'Sunday', 'sonntag': 'Sunday', 'sun': 'Sunday', 'so': 'Sunday', '7': 'Sunday', '7.0': 'Sunday', '0': 'Sunday'
            }
            
            df_hist['standard_day'] = df_hist[day_col].astype(str).str.strip().str.lower().map(day_translation)
            
            def time_to_bucket(t_val):
                try:
                    if pd.isna(t_val):
                        return None
                    if hasattr(t_val, 'hour') and hasattr(t_val, 'minute'):
                        h = t_val.hour
                        m = t_val.minute
                    else:
                        t_str = str(t_val).strip()
                        parts = t_str.split(':')
                        h = int(parts[0])
                        m = int(parts[1]) if len(parts) > 1 else 0
                    
                    total_mins = h * 60 + m
                    bucket_mins = (total_mins // 30) * 30
                    bh = bucket_mins // 60
                    bm = bucket_mins % 60
                    res = f"{bh:02d}:{bm:02d}"
                    return res if res in intervals else None
                except:
                    return None

            df_hist['bucket_interval'] = df_hist[time_col].apply(time_to_bucket)
            df_hist['numeric_vq'] = pd.to_numeric(df_hist[vq_col], errors='coerce').fillna(0)
            
            for std_day in days_list:
                sub_df = df_hist[df_hist['standard_day'] == std_day]
                if not sub_df.empty:
                    grouped = sub_df.groupby('bucket_interval')['numeric_vq'].sum().to_dict()
                    daily_absolute_curves[std_day] = {interval: grouped.get(interval, 0.0) for interval in intervals}
                else:
                    daily_absolute_curves[std_day] = default_day_profile[std_day]
            file_parsed = True
            st.sidebar.success("✅ Successfully loaded exact VQ Entered absolute values from file!")
        else:
            st.sidebar.warning("⚠️ Could not match required columns in file. Using default profiles.")
    except Exception as e:
        st.sidebar.error(f"❌ Error reading file: {e}")

if not file_parsed:
    for day in days_list:
        daily_absolute_curves[day] = default_day_profile[day]

weekday_abbr_map = {0: "Mo", 1: "Tu", 2: "We", 3: "Th", 4: "Fr", 5: "Sa", 6: "Su"}
weekday_full_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}

# Calculate total month calls directly from the historical file sums for executive metrics
total_monthly_calls_sum = 0
for dt in date_list:
    day_full = weekday_full_map[dt.weekday()]
    total_monthly_calls_sum += sum(daily_absolute_curves[day_full].values())

total_monthly_workload_mins = total_monthly_calls_sum * (aht / 60)
gross_workload_hours = (total_monthly_workload_mins / 60) / (1 - (total_shrinkage / 100))
required_fte = round(gross_workload_hours / 168, 2)

st.subheader(f"📊 Executive Overview — {selected_month_name} {year} (Derived from File)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Monthly Calls", f"{int(total_monthly_calls_sum):,}")
col2.metric("Required Capacity", f"{required_fte} FTE")
col3.metric("Target SL", f"{target_sl}% in {target_time}s")
col4.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

st.markdown("---")

# Build matrices directly using exact absolute values from file
dict_mins = {interval: {} for interval in intervals}
dict_calls = {interval: {} for interval in intervals}
dict_net = {interval: {} for interval in intervals}
dict_gross = {interval: {} for interval in intervals}

for dt in date_list:
    date_str = f"{dt.day:02d}"
    day_abbr = weekday_abbr_map[dt.weekday()]
    day_full = weekday_full_map[dt.weekday()]
    
    col_tuple = (date_str, day_abbr)
    day_profile = daily_absolute_curves[day_full]
    
    for interval in intervals:
        int_calls = day_profile.get(interval, 0.0)
        int_mins = int_calls * (aht / 60)
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
# TAB 1: MATRIX & EXPORT BUTTON
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

    st.markdown("---")
    st.subheader("📥 Export CSV for Swisscom (Account CT # 1427)")

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        exporter_role = st.selectbox("Who is exporting?", ["Vali", "Colleague"])
    with col_exp2:
        if exporter_role == "Vali":
            export_filename = "FC_NICE04A_102578321_Swissccom.csv"
            st.info(f"Filename: `{export_filename}`")
        else:
            colleague_prefix = st.text_input("Enter Colleague File Prefix:", value="FC_NICE04A_Colleague")
            export_filename = f"{colleague_prefix}_Swissccom.csv"

    export_rows = []
    for dt in date_list:
        date_str = f"{dt.month}/{dt.day}/{dt.year}"
        day_full = weekday_full_map[dt.weekday()]
        day_profile = daily_absolute_curves[day_full]
        
        for interval in intervals:
            int_calls = day_profile.get(interval, 0.0)
            h, m = map(int, interval.split(":"))
            t_obj = datetime.time(h, m)
            t_12hr = t_obj.strftime("%I:%M %p").lstrip("0")
            
            export_rows.append({
                "CT #": 1427,
                "Date": date_str,
                "Interval": t_12hr,
                "Contacts Rec": round(int_calls, 6),
                "AHT": int(aht)
            })

    df_export = pd.DataFrame(export_rows)
    csv_bytes = df_export.to_csv(index=False).encode('utf-8')

    st.download_button(
        label="📥 Download Swisscom CSV Export",
        data=csv_bytes,
        file_name=export_filename,
        mime="text/csv",
        help="Download CSV file formatted for Swisscom WFM."
    )

# ---------------------------------------------------------
# TAB 2: CHART
# ---------------------------------------------------------
with tab2:
    st.header(f"📈 Daily Interval Workload Chart — {selected_month_name} {year}")
    selected_chart_idx = st.slider("Select Day to Plot:", 1, len(date_list), 1)
    
    dt_chart = date_list[selected_chart_idx - 1]
    col_tuple_chart = (f"{dt_chart.day:02d}", weekday_abbr_map[dt_chart.weekday()])
    
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
