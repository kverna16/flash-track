"""
FlashTrack dashboard.

Visualizes flash (projected) vs. actual revenue/attendance, pulling directly
from the daily_variance and flagged_anomalies views in Postgres.

Run with: streamlit run dashboard.py
"""

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine

DB_CONN_STRING = "postgresql+psycopg2://flashtrack:flashtrack_dev_pw@localhost:5432/flashtrack"

st.set_page_config(page_title="FlashTrack", layout="wide")


@st.cache_resource
def get_engine():
    return create_engine(DB_CONN_STRING)


@st.cache_data(ttl=60)
def load_variance_data():
    engine = get_engine()
    return pd.read_sql("SELECT * FROM daily_variance ORDER BY date", engine)


@st.cache_data(ttl=60)
def load_anomalies():
    engine = get_engine()
    return pd.read_sql("SELECT * FROM flagged_anomalies ORDER BY date DESC", engine)


st.title("FlashTrack — Flash vs. Actual Reconciliation")
st.caption("Automated reconciliation of projected (flash) vs. actual daily revenue and attendance.")

df = load_variance_data()
anomalies_df = load_anomalies()

# --- Filters ---
locations = ["All locations"] + sorted(df["location_name"].unique().tolist())
selected_location = st.selectbox("Location", locations)

filtered = df if selected_location == "All locations" else df[df["location_name"] == selected_location]

# --- Summary metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Actual Revenue", f"${filtered['actual_revenue'].sum():,.0f}")
col2.metric("Total Projected Revenue", f"${filtered['projected_revenue'].sum():,.0f}")
col3.metric("Avg. Revenue Variance", f"{filtered['revenue_variance_pct'].mean():.1f}%")
col4.metric("Flagged Anomaly Days", len(anomalies_df) if selected_location == "All locations"
            else len(anomalies_df[anomalies_df["location_name"] == selected_location]))

st.divider()

# --- Flash vs actual trend ---
st.subheader("Flash vs. Actual Revenue Over Time")
trend_df = filtered.melt(
    id_vars=["date"],
    value_vars=["projected_revenue", "actual_revenue"],
    var_name="metric",
    value_name="revenue",
)
fig_trend = px.line(
    trend_df, x="date", y="revenue", color="metric",
    labels={"revenue": "Revenue ($)", "date": "Date", "metric": "Metric"},
)
st.plotly_chart(fig_trend, use_container_width=True)

# --- Variance by location ---
st.subheader("Average Revenue Variance by Location")
by_location = df.groupby("location_name", as_index=False)["revenue_variance_pct"].mean()
fig_bar = px.bar(
    by_location, x="location_name", y="revenue_variance_pct",
    labels={"revenue_variance_pct": "Avg. Variance (%)", "location_name": "Location"},
    color="revenue_variance_pct", color_continuous_scale="RdYlGn_r",
)
st.plotly_chart(fig_bar, use_container_width=True)

# --- Flagged anomalies table ---
st.subheader("Flagged Anomalies (>= 15% variance)")
if anomalies_df.empty:
    st.info("No anomalies currently flagged.")
else:
    display_df = anomalies_df[[
        "date", "location_name", "projected_revenue", "actual_revenue",
        "revenue_variance_pct", "anomaly_type",
    ]]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
