import calendar
import datetime
import math
import re

import numpy as np
import pandas as pd
import streamlit as st

# =========================================================
# CORE CALCULATION FUNCTIONS
# =========================================================
INTERVAL_SECONDS = 1800  # 30-minute intervals
INTERVALS = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 30)]  # 07:00 - 21:30
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_FULL = {i: d for i, d in enumerate(DAYS)}
WEEKDAY_ABBR = {0: "Mo", 1: "Tu", 2: "We", 3: "Th", 4: "Fr", 5: "Sa", 6: "Su"}

DAY_TRANSLATION = {
    'monday': 'Monday', 'montag': 'Monday', 'mon': 'Monday', 'mo': 'Monday', '1': 'Monday', '1.0': 'Monday',
    'tuesday': 'Tuesday', 'dienstag': 'Tuesday', 'tu': 'Tuesday', 'tue': 'Tuesday', 'di': 'Tuesday', '2': 'Tuesday', '2.0': 'Tuesday',
    'wednesday': 'Wednesday', 'mittwoch': 'Wednesday', 'we': 'Wednesday', 'wed': 'Wednesday', 'mi': 'Wednesday', '3': 'Wednesday', '3.0': 'Wednesday',
    'thursday': 'Thursday', 'donnerstag': 'Thursday', 'th': 'Thursday', 'thu': 'Thursday', 'do': 'Thursday', '4': 'Thursday', '4.0': 'Thursday',
    'friday': 'Friday', 'freitag': 'Friday', 'fri': 'Friday', 'fr': 'Friday', '5': 'Friday', '5.0': 'Friday',
    'saturday': 'Saturday', 'samstag': 'Saturday', 'sat': 'Saturday', 'sa': 'Saturday', '6': 'Saturday', '6.0': 'Saturday',
    'sunday': 'Sunday', 'sonntag': 'Sunday', 'su': 'Sunday', 'sun': 'Sunday', 'so': 'Sunday', '7': 'Sunday', '7.0': 'Sunday', '0': 'Sunday', '0.0': 'Sunday',
}

DEFAULT_PROFILE = {
    "Monday": 40.0, "Tuesday": 40.0, "Wednesday": 40.0, "Thursday": 40.0,
    "Friday": 40.0, "Saturday": 20.0, "Sunday": 15.0,
}


def normalize_day(val):
    """Map a weekday text/number (EN/DE) to a full English weekday name."""
    if pd.isna(val):
        return None
    return DAY_TRANSLATION.get(str(val).strip().lower().rstrip('.'))


def time_to_bucket(t_val):
    """Convert many time formats to a 30-minute bucket label like '08:30'."""
    try:
        if t_val is None or (not isinstance(t_val, str) and pd.isna(t_val)):
            return None
        if hasattr(t_val, 'hour') and hasattr(t_val, 'minute'):
            total = t_val.hour * 60 + t_val.minute
        elif isinstance(t_val, (int, float, np.integer, np.floating)):
            f = float(t_val)
            if 0 <= f < 1:  # Excel stores times as a fraction of a day
                total = int(round(f * 24 * 60))
            elif f == int(f) and 1 <= f <= 24:  # plain hour number
                total = int(f) * 60
            else:
                return None
        else:
            m = re.search(r'(\d{1,2}):(\d{2})', str(t_val))
            if not m:
                return None
            hour, minute = int(m.group(1)), int(m.group(2))
            if hour > 23 or minute > 59:
                return None
            total = hour * 60 + minute
        bucket = (total // 30) * 30
        label = f"{bucket // 60:02d}:{bucket % 60:02d}"
        return label if 0 <= total < 1440 and label in INTERVALS else None
    except Exception:
        return None


def find_column(columns_lower, keys, exclude=()):
    for name, orig in columns_lower.items():
        if orig in exclude:
            continue
        if any(k in name for k in keys):
            return orig
    return None


def read_table(uploaded_file):
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file, sep=None, engine="python")  # auto-detects ; or ,
    return pd.read_excel(uploaded_file)


def read_history_table(uploaded_file):
    """Find a detailed history table without importing pivot totals twice."""
    if uploaded_file.name.lower().endswith(".csv"):
        result = read_table(uploaded_file)
        result.attrs["source_sheet"] = "CSV"
        result.attrs["header_row"] = 1
        return result
    book = pd.ExcelFile(uploaded_file)
    candidates = []
    for sheet in book.sheet_names:
        preview = pd.read_excel(book, sheet_name=sheet, header=None, nrows=25)
        for row_idx, row in preview.iterrows():
            labels = [str(v).strip().lower() for v in row if pd.notna(v)]
            has_time = any(any(k in v for k in ["intervall", "interval", "zeit", "time", "start"]) for v in labels)
            has_volume = any(any(k in v for k in ["entered", "offered", "contacts", "calls", "volume", "anrufe", "eingang"]) for v in labels)
            has_day = any(v in ["day", "date", "datum", "weekday", "wochentag", "day of week"]
                          or "date" in v or "datum" in v for v in labels)
            if has_time and has_volume and has_day:
                candidates.append((sheet, int(row_idx)))
                break
    if len(candidates) != 1:
        raise ValueError(
            "Expected one detailed history table with time, date/weekday and offered calls; "
            f"found {len(candidates)}. Sheets: {', '.join(book.sheet_names)}. "
            "For multiple history tables, upload the required table as a separate file.")
    sheet, header = candidates[0]
    result = pd.read_excel(book, sheet_name=sheet, header=header)
    result.columns = [str(c).strip() for c in result.columns]
    result = result.dropna(how="all")
    result.attrs["source_sheet"] = sheet
    result.attrs["header_row"] = header + 1
    return result


def build_weekday_curves(df_hist, aggregation="Mean", weeks_in_file=1, drop_zero_days=True):
    """
    Turn raw history into ONE typical day per weekday (calls per 30-min interval).

    - If the file has a date column: sum all rows per (date, interval), then take the
      MEAN (or MEDIAN) across all dates of the same weekday.
    - If it only has a weekday column: sum per (weekday, interval) and divide by
      'weeks_in_file' (the number of weeks the file covers).
    """
    cols = {str(c).strip().lower(): c for c in df_hist.columns}
    date_col = find_column(cols, ['datum', 'date'])
    # NICE exports may label the actual date "Day" and weekday text "Day Of Week".
    if date_col is None and "day" in cols:
        candidate = cols["day"]
        values = df_hist[candidate].dropna()
        if pd.api.types.is_datetime64_any_dtype(values) or (
            len(values) and values.map(lambda v: isinstance(v, (datetime.date, datetime.datetime))
                or bool(re.match(r"^(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4})", str(v).strip()))).all()
        ):
            date_col = candidate
    time_col = find_column(cols, ['intervall', 'interval', 'zeit', 'time', 'start'],
                           exclude=[date_col] if date_col is not None else [])
    if time_col is None and date_col is not None:
        time_col = date_col  # a single datetime column
    used = [c for c in (date_col, time_col) if c is not None]
    day_col = None
    if date_col is None:
        day_col = find_column(cols, ['wochentag', 'weekday', 'day', 'tag'], exclude=used)
    vq_col = (find_column(cols, ['vq entered', 'entered'], exclude=used)
              or find_column(cols, ['vq', 'offered', 'contacts', 'calls', 'volume', 'anrufe', 'eingang'], exclude=used))

    if time_col is None or vq_col is None or (date_col is None and day_col is None):
        raise ValueError(
            "Could not match the needed columns (interval/time, date or weekday, VQ entered). "
            f"Columns found: {list(df_hist.columns)}"
        )

    df = df_hist.copy()
    diag = {
        "date_col": date_col, "time_col": time_col, "day_col": day_col, "vq_col": vq_col,
        "rows_total": len(df),
        "source_sheet": df_hist.attrs.get("source_sheet", "Table"),
        "header_row": df_hist.attrs.get("header_row", 1),
    }

    df["_bucket"] = df[time_col].apply(time_to_bucket)
    df["_vq"] = pd.to_numeric(df[vq_col], errors="coerce")
    diag["rows_bad_time"] = int(df["_bucket"].isna().sum())
    diag["rows_bad_vq"] = int(df["_vq"].isna().sum())
    if diag["rows_bad_vq"] or (df["_vq"] < 0).any() or not np.isfinite(df["_vq"]).all():
        raise ValueError("Call volumes must be numeric and non-negative. Check decimal/thousands separators and empty cells.")
    if diag["rows_bad_time"]:
        raise ValueError(f"{diag['rows_bad_time']} rows have invalid times or fall outside 07:00–22:00. Correct the file or account opening hours before forecasting.")

    if date_col is not None:
        df["_date"] = df[date_col].apply(
            lambda v: pd.to_datetime(v, errors="coerce", dayfirst=False)
            if re.match(r"^\d{4}-\d{2}-\d{2}", str(v))
            else pd.to_datetime(v, errors="coerce", dayfirst=True)
        ).dt.normalize()
        diag["rows_bad_day"] = int(df["_date"].isna().sum())
        if diag["rows_bad_day"]:
            raise ValueError("History contains invalid dates. Use unambiguous YYYY-MM-DD dates.")
        df = df.dropna(subset=["_bucket", "_date"])
        diag["rows_used"] = len(df)

        pivot = (df.groupby(["_date", "_bucket"])["_vq"].sum()
                 .unstack(fill_value=0)
                 .reindex(columns=INTERVALS, fill_value=0))
        diag["dates_in_file"] = len(pivot)
        if drop_zero_days:
            before = len(pivot)
            pivot = pivot[pivot.sum(axis=1) > 0]
            diag["zero_days_dropped"] = before - len(pivot)
        weekday_series = pd.Series(pivot.index.dayofweek, index=pivot.index).map(WEEKDAY_FULL)

        curves, n_dates = {}, {}
        for day in DAYS:
            sub = pivot[weekday_series == day]
            n_dates[day] = len(sub)
            if len(sub):
                agg = sub.median() if aggregation == "Median" else sub.mean()
                curves[day] = {i: float(agg[i]) for i in INTERVALS}
            else:
                curves[day] = {i: 0.0 for i in INTERVALS}
        diag["dates_per_weekday"] = n_dates
    else:
        df["_day"] = df[day_col].apply(normalize_day)
        diag["rows_bad_day"] = int(df["_day"].isna().sum())
        if diag["rows_bad_day"]:
            raise ValueError("History contains unrecognised weekdays. Use Monday–Sunday or Montag–Sonntag.")
        df = df.dropna(subset=["_bucket", "_day"])
        diag["rows_used"] = len(df)
        weeks = max(float(weeks_in_file), 1.0)
        grouped = df.groupby(["_day", "_bucket"])["_vq"].sum() / weeks
        curves, n_dates = {}, {}
        for day in DAYS:
            if day in grouped.index.get_level_values(0):
                g = grouped.loc[day].to_dict()
                curves[day] = {i: float(g.get(i, 0.0)) for i in INTERVALS}
                n_dates[day] = int(weeks)
            else:
                curves[day] = {i: 0.0 for i in INTERVALS}
                n_dates[day] = 0
        diag["dates_per_weekday"] = n_dates

    diag["source_calls"] = float(df["_vq"].sum())
    diag["missing_weekdays"] = [d for d in DAYS if diag["dates_per_weekday"].get(d, 0) == 0]
    return curves, diag


def erlang_c(n, a):
    """Probability that a call has to wait (Erlang C). n = agents, a = traffic in Erlangs."""
    if n <= a:
        return 1.0
    b = 1.0
    for i in range(1, n + 1):  # numerically stable Erlang B recursion
        b = a * b / (i + a * b)
    return n * b / (n - a * (1 - b))


def service_level(n, a, aht, target_sec):
    if n <= a:
        return 0.0
    return 1 - erlang_c(n, a) * math.exp(-(n - a) * target_sec / aht)


def agents_required(calls, aht, target_sl, target_sec, max_occ):
    """Minimum agents on queue to hit the SL target and stay below max occupancy."""
    if not (math.isfinite(calls) and math.isfinite(aht)) or calls < 0 or aht <= 0:
        raise ValueError("Calls must be finite and non-negative; AHT must be positive.")
    if not (0 < target_sl < 1 and target_sec >= 0 and 0 < max_occ <= 1):
        raise ValueError("SL must be below 100%, answer time non-negative, occupancy in (0, 100%].")
    if calls == 0:
        return 0
    if calls == 0:
        return 0
    if calls == 0:
        return 0
    a = calls * aht / INTERVAL_SECONDS
    n = max(1, int(math.floor(a)) + 1)
    while n < 10000:
        if service_level(n, a, aht, target_sec) >= target_sl and (a / n) <= max_occ:
            return n
        n += 1
    raise ValueError("Staffing search limit reached. Check input units and volume.")


# =========================================================
# UI
# =========================================================
st.set_page_config(page_title="Ohara WFM - Swisscom Engine", layout="wide")
st.title("🧙‍♂️ Ohara - Swisscom Strategic WFM Engine")
st.markdown("Historical Distribution & Staffing Requirements • Rotation Preview")

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
st.sidebar.header("📅 Planning Period")
month_names = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
selected_month_name = st.sidebar.selectbox("Select Planning Month", month_names, index=11)
month_num = month_names.index(selected_month_name) + 1
year = int(st.sidebar.number_input("Year", min_value=2024, max_value=2035, value=2026, step=1))

st.sidebar.header("⚙️ Account Parameters")
aht = st.sidebar.number_input("Average Handle Time (Seconds)", min_value=1, value=600, step=10)
target_sl = st.sidebar.slider("Target Service Level (%)", 50, 99, 80)
target_time = st.sidebar.number_input("Target Answer Time (Seconds)", min_value=0, value=20)
max_occ_pct = st.sidebar.slider("Max Occupancy (%)", 50, 100, 85)
ioo = st.sidebar.number_input("In-Office Overhead (%)", min_value=0.0, max_value=99.0, value=14.33)
ooo = st.sidebar.number_input("Out-of-Office Overhead (%)", min_value=0.0, max_value=99.0, value=16.0)
shrinkage_basis = st.sidebar.selectbox(
    "Shrinkage basis", ["Same base: add IOO + OOO", "Sequential: IOO after OOO"],
    help="Use addition only if both percentages refer to the same contracted-hours base. Sequential means IOO is a share of attendance hours.")
total_shrinkage = (ioo + ooo if shrinkage_basis.startswith("Same")
                   else 100 * (1 - (1 - ioo / 100) * (1 - ooo / 100)))
if total_shrinkage >= 100:
    st.error("Combined shrinkage must be below 100%.")
    st.stop()
weekly_contract_hours = st.sidebar.number_input("Contract hours per FTE per week", min_value=0.5, value=40.0, step=0.5)

st.sidebar.header("📈 Forecast Settings")
monthly_target = st.sidebar.number_input(
    "Forecast calls for the selected month (0 = use history)", min_value=0, value=0, step=1000,
    help="If you enter a monthly forecast, it is spread over the days and intervals using the "
         "historical weekday weights and interval shares. 0 = use the historical daily average as is."
)
aggregation = st.sidebar.selectbox("History aggregation per weekday", ["Mean", "Median"],
                                   help="Median is more robust against outlier days (outages, campaigns).")
drop_zero_days = st.sidebar.checkbox("Ignore dates with 0 calls in history", value=True)
weeks_in_file = st.sidebar.number_input(
    "Weeks covered by file (only if file has NO date column)", min_value=1, value=1, step=1)

st.sidebar.header("🔄 Rotation Cycle")
rotation_weeks = st.sidebar.slider("Rotation Cycle Length (Weeks)", 2, 10, 10)

st.sidebar.header("📁 Data Sources")
verteilung_file = st.sidebar.file_uploader("Upload 'Copy of Swisscom - Call verteilung 2' (.xlsx/.csv)",
                                           type=["xlsx", "csv"], key="verteilung")
verfuegbarkeit_file = st.sidebar.file_uploader("Upload Verfügbarkeitsliste (.xlsx/.csv)",
                                               type=["xlsx", "csv"], key="verfuegbarkeit")

st.markdown("---")

# ---------------------------------------------------------
# CALENDAR (1st of month to the final Sunday)
# ---------------------------------------------------------
days_in_month = calendar.monthrange(year, month_num)[1]
start_date = datetime.date(year, month_num, 1)
end_of_month_date = datetime.date(year, month_num, days_in_month)
end_date = end_of_month_date + datetime.timedelta(days=(6 - end_of_month_date.weekday()) % 7)

date_list = []
curr = start_date
while curr <= end_date:
    date_list.append(curr)
    curr += datetime.timedelta(days=1)
in_month_dates = [d for d in date_list if d.month == month_num]

# ---------------------------------------------------------
# HISTORY -> TYPICAL DAY PER WEEKDAY
# ---------------------------------------------------------
daily_curves = {day: {i: DEFAULT_PROFILE[day] for i in INTERVALS} for day in DAYS}
diag = None
file_parsed = False

if verteilung_file is not None:
    try:
        df_hist = read_history_table(verteilung_file)
        daily_curves, diag = build_weekday_curves(df_hist, aggregation, weeks_in_file, drop_zero_days)
        file_parsed = True
        st.sidebar.success("✅ History loaded and averaged per weekday.")
    except Exception as e:
        st.sidebar.error(f"❌ Error reading file: {e}")
        st.stop()

if file_parsed and diag["missing_weekdays"]:
    st.warning("Missing history for: " + ", ".join(diag["missing_weekdays"]))
    if not st.checkbox("I confirm these weekdays are closed and should receive zero calls"):
        st.info("Add history for these weekdays, or confirm that they are closed.")
        st.stop()
if not file_parsed:
    st.warning("DEMO DATA — upload history before using results for planning.")
    st.sidebar.info("No valid history loaded – using default demo profile.")

# ---------------------------------------------------------
# FORECAST: scale history to the monthly target (if given)
# ---------------------------------------------------------
history_month_calls = sum(sum(daily_curves[WEEKDAY_FULL[d.weekday()]].values()) for d in in_month_dates)
if history_month_calls <= 0:
    st.error("No positive historical volume is available for this month. Check the history and selected period.")
    st.stop()
scale = (monthly_target / history_month_calls) if (monthly_target > 0 and history_month_calls > 0) else 1.0

forecast = {}  # date -> {interval: calls}
for dt in date_list:
    base = daily_curves[WEEKDAY_FULL[dt.weekday()]]
    forecast[dt] = {i: base.get(i, 0.0) * scale for i in INTERVALS}

# ---------------------------------------------------------
# MATRICES
# ---------------------------------------------------------
dict_mins = {i: {} for i in INTERVALS}
dict_calls = {i: {} for i in INTERVALS}
dict_net = {i: {} for i in INTERVALS}
dict_gross = {i: {} for i in INTERVALS}

for dt in date_list:
    col_tuple = (f"{dt.day:02d}", WEEKDAY_ABBR[dt.weekday()])
    for interval in INTERVALS:
        calls = forecast[dt][interval]
        net = agents_required(calls, aht, target_sl / 100, target_time, max_occ_pct / 100)
        gross = math.ceil(net / (1 - total_shrinkage / 100)) if net > 0 else 0
        dict_mins[interval][col_tuple] = round(calls * aht / 60, 1)
        dict_calls[interval][col_tuple] = round(calls, 1)
        dict_net[interval][col_tuple] = net
        dict_gross[interval][col_tuple] = gross

df_matrix_mins = pd.DataFrame(dict_mins).T
df_matrix_calls = pd.DataFrame(dict_calls).T
df_matrix_net = pd.DataFrame(dict_net).T
df_matrix_gross = pd.DataFrame(dict_gross).T
columns_multiindex = pd.MultiIndex.from_tuples(df_matrix_mins.columns, names=["Date", "Day"])
for _df in (df_matrix_mins, df_matrix_calls, df_matrix_net, df_matrix_gross):
    _df.columns = columns_multiindex

# ---------------------------------------------------------
# EXECUTIVE METRICS (only days that belong to the selected month)
# ---------------------------------------------------------
total_monthly_calls = sum(sum(forecast[d].values()) for d in in_month_dates)
workload_hours = total_monthly_calls * aht / 3600
fte_hours_month = weekly_contract_hours * days_in_month / 7
required_fte_workload = workload_hours / (1 - total_shrinkage / 100) / fte_hours_month

in_month_cols = [(f"{d.day:02d}", WEEKDAY_ABBR[d.weekday()]) for d in in_month_dates]
gross_agent_halfhours = df_matrix_gross[in_month_cols].to_numpy().sum()
required_fte_erlang = (gross_agent_halfhours * 0.5) / fte_hours_month

st.subheader(f"📊 Executive Overview — {selected_month_name} {year}")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Monthly Calls", f"{int(round(total_monthly_calls)):,}")
c2.metric("FTE (workload only)", f"{required_fte_workload:.2f}")
c3.metric("FTE (Erlang C, SL-based)", f"{required_fte_erlang:.2f}",
          help="Interval-by-interval staffing that actually meets the service level target. "
               "This is an interval staffing-hours estimate, not a feasible roster. Shift patterns, breaks, skills and leave can increase the roster requirement.")
c4.metric("Target SL", f"{target_sl}% in {target_time}s")
c5.metric("Total Shrinkage", f"{round(total_shrinkage, 2)}%")

with st.expander("🔎 Data check — what did the app read from your file?", expanded=(diag is not None)):
    if diag is None:
        st.write("No file loaded. Demo profile is used.")
    else:
        st.write(f"**Source:** `{diag['source_sheet']}`, header row {diag['header_row']} | "
                 f"**Offered calls read:** {diag['source_calls']:,.0f}")
        st.caption("15-minute rows are summed into 30-minute buckets before averaging dates of the same weekday. Dates entirely absent from the file are not assumed to be zero-call days.")
        st.write(f"**Columns used** → time: `{diag['time_col']}` | "
                 f"date: `{diag['date_col']}` | weekday: `{diag['day_col']}` | VQ: `{diag['vq_col']}`")
        st.write(f"Rows in file: **{diag['rows_total']:,}** | rows used: **{diag['rows_used']:,}** | "
                 f"bad time: {diag['rows_bad_time']:,} | bad date/weekday: {diag['rows_bad_day']:,} | "
                 f"non-numeric VQ: {diag['rows_bad_vq']:,}")
        if diag.get("dates_in_file") is not None:
            st.write(f"Distinct dates in history: **{diag['dates_in_file']}** "
                     f"(zero-call days dropped: {diag.get('zero_days_dropped', 0)})")
        else:
            st.warning("File has no date column → totals were divided by 'Weeks covered by file' in the sidebar. "
                       "Make sure that number is correct.")
        if diag["missing_weekdays"]:
            st.warning(f"No history for: {', '.join(diag['missing_weekdays'])} → zero calls, only after explicit closed-day confirmation.")
        summary = pd.DataFrame({
            "Dates/weeks used": [diag["dates_per_weekday"][d] for d in DAYS],
            "Avg calls per day": [round(sum(daily_curves[d].values()), 1) for d in DAYS],
        }, index=DAYS)
        st.dataframe(summary, use_container_width=True)
    if monthly_target > 0:
        st.info(f"Monthly forecast {monthly_target:,} vs. history-based {int(round(history_month_calls)):,} "
                f"→ scale factor {scale:.3f}")

st.markdown("---")

# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🧮 Monthly Distribution Matrix",
    "📈 Staffing Requirements",
    "📋 Agent File Preview",
    "🔄 Rotation Example"
])

with tab1:
    st.header(f"🧮 Monthly Calendar Matrix — {selected_month_name} {year}")
    st.write("Vertical: 30-minute intervals (07:00 – 22:00) | Row 1: Calendar Date | Row 2: Weekday Abbreviation "
             "| Days after month end are only shown to complete the last week.")

    metric_choice = st.radio(
        "Select Display Metric:",
        ["Workload Minutes (Min)", "Call Volume (Calls)", "Net Required FTE", "Gross Required FTE (with Shrinkage)"],
        horizontal=True
    )

    if metric_choice == "Workload Minutes (Min)":
        show = df_matrix_mins.copy()
        show.loc["Total"] = show.sum()
        st.dataframe(show, use_container_width=True)
    elif metric_choice == "Call Volume (Calls)":
        show = df_matrix_calls.copy()
        show.loc["Total"] = show.sum()
        st.dataframe(show, use_container_width=True)
    elif metric_choice == "Net Required FTE":
        st.dataframe(df_matrix_net, use_container_width=True)
    else:
        st.dataframe(df_matrix_gross, use_container_width=True)

    st.markdown("---")
    st.subheader("📥 Forecast CSV Export")
    st.caption("Forecast contacts and AHT only; this does not export agent schedules or days off. Confirm the format with your NICE import configuration.")
    export_ct = int(st.number_input("Call Type ID", min_value=1, value=1427))
    include_trailing = st.checkbox("Include days after month end to complete the last week", value=False)
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
    for dt in (date_list if include_trailing else in_month_dates):
        date_str = f"{dt.month}/{dt.day}/{dt.year}"
        for interval in INTERVALS:
            h, m = map(int, interval.split(":"))
            t_12hr = datetime.time(h, m).strftime("%I:%M %p").lstrip("0")
            export_rows.append({
                "CT #": export_ct,
                "Date": date_str,
                "Interval": t_12hr,
                "Contacts Rec": round(forecast[dt][interval], 6),
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

with tab2:
    st.header(f"📈 Daily Interval Workload Chart — {selected_month_name} {year}")
    selected_chart_idx = st.slider("Select Day to Plot:", 1, len(date_list), 1)
    dt_chart = date_list[selected_chart_idx - 1]
    col_tuple_chart = (f"{dt_chart.day:02d}", WEEKDAY_ABBR[dt_chart.weekday()])
    st.caption(f"{dt_chart.strftime('%A, %d.%m.%Y')} — "
               f"{int(round(sum(forecast[dt_chart].values()))):,} calls forecast")
    df_chart_plot = pd.DataFrame({
        "Gross Required FTE": df_matrix_gross[col_tuple_chart],
        "Net On-Queue FTE Target": df_matrix_net[col_tuple_chart]
    }, index=INTERVALS)
    st.line_chart(df_chart_plot)
    st.caption("Required staffing only. Scheduled staffing and actual available capacity are not yet loaded.")

with tab3:
    st.header("📋 Agent File Preview")
    st.info("This version previews the file only. Agent constraints are not yet applied to staffing or rotations.")
    if verfuegbarkeit_file is not None:
        try:
            df_agents = read_table(verfuegbarkeit_file)
            st.success("Loaded Verfügbarkeitsliste!")
            st.dataframe(df_agents, use_container_width=True)
        except Exception as e:
            st.error(f"Error parsing file: {e}")
    else:
        st.info("💡 Upload `Verfügbarkeitsliste.xlsx` in the sidebar to auto-populate exact agent names.")

with tab4:
    st.header(f"🔄 Rotation Example ({rotation_weeks}-Week Cycle)")
    st.warning("Illustration only: not calculated from agent availability, skills, contracts or demand. Do not use as an approved schedule.")
    st.markdown("""
**Color-Coded Shift Legend:**
* 🔵 **Morning:** `07:00 - 15:30` | 🟢 **Day:** `08:30 - 17:00` | 🟠 **Evening:** `12:00 - 20:30` | 🟣 **Late Evening:** `13:30 - 22:00` | 🔷 **EoB Closing:** `14:00 - 22:00`
""")
    selected_week = st.selectbox("Select Week to View Daily Coverage (Mon - Sun):",
                                 [f"Week {w}" for w in range(1, rotation_weeks + 1)])
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

    for day in DAYS:
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
