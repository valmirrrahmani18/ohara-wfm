import streamlit as st

st.set_page_config(page_title="Ohara WFM Assistant", layout="wide")

st.title("🧙‍♂️ Ohara - Swisscom WFM Strategic Assistant")
st.markdown("Automated Shift Scheduling & Strategic Capacity Planning")

# Sidebar Configuration
st.sidebar.header("Account Parameters")
call_volume = st.sidebar.number_input("Monthly Call Volume (Minutes)", value=340000, step=10000)
aht = st.sidebar.number_input("Average Handle Time (Seconds)", value=600, step=10)
target_sl = st.sidebar.slider("Target Service Level (%)", 50, 100, 80)
ioo = st.sidebar.number_input("In-Office Overhead (%)", value=14.33)
ooo = st.sidebar.number_input("Out-of-Office Overhead (%)", value=16.0)

st.subheader("📊 Strategic WFM Summary")
col1, col2, col3 = st.columns(3)
col1.metric("Active Roster Size", "70 Agents")
col2.metric("Target SL", f"{target_sl}/20")
col3.metric("Total Shrinkage", f"{round(ioo + ooo, 2)}%")

st.success("Ohara Cloud Engine is active and ready for scenario analysis!")
