import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import sqlitecloud
from collections import defaultdict
import base64

# Set page layout and design
st.set_page_config(layout="wide", page_title="Bird Migration Tracker", page_icon="🕊️")
st.markdown("""
    <style>
        .block-container {
            padding-top: 2.7rem !important;
            padding-bottom: 0rem !important;
        }
        section[data-testid="stSidebar"] {
            min-width: 320px !important;
            max-width: 320px !important;
            width: 320px !important;
            visibility: visible !important;
            transform: none !important;
            position: relative !important;
        }
        [data-testid="collapsedControl"] {
            display: none;
        }
        .stDataFrame { margin-top: -40px; } /* reduce space between map and table */
    </style>
""", unsafe_allow_html=True)

st.title("Bird Migration Visualization 🕊️")
st.markdown("Track bird movements across time and space using cloud-processed predictions.")

# Load API key securely
def load_api_key():
    try:
        with open("apikey.txt", "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        st.error("API key file 'apikey.txt' not found.")
        return None

api_key = load_api_key()

if api_key:
    @st.cache_data(ttl=30)
    def load_data():
        conn = sqlitecloud.connect(f"sqlitecloud://cks7jse1nz.g1.sqlite.cloud:8860/birds.db?apikey={api_key}")
        query = "SELECT * FROM detections"
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    df = load_data()

    df.rename(columns={
        'Com_Name': 'common_name',
        'Lat': 'latitude',
        'Lon': 'longitude',
        'Date': 'date'
    }, inplace=True)

    required_cols = {"common_name", "latitude", "longitude", "date"}
    if not required_cols.issubset(df.columns):
        st.error("Database must contain columns: common_name, latitude, longitude, date")
    else:
        df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['Time'], errors='coerce')
        df.dropna(subset=['timestamp', 'latitude', 'longitude'], inplace=True)

        # Sidebar
        st.sidebar.title("Filter Options 🔍")
        bird_list = sorted(df['common_name'].unique())
        selected_bird = st.sidebar.selectbox("Select Bird", bird_list)

        filter_type = st.sidebar.radio("Select Time Filter", ["Date Range", "Year", "All Time"])

        if filter_type == "Date Range":
            min_date, max_date = df['timestamp'].min(), df['timestamp'].max()
            from_date = st.sidebar.date_input("From", min_value=min_date.date(), value=min_date.date())
            to_date = st.sidebar.date_input("To", min_value=min_date.date(), max_value=max_date.date(), value=max_date.date())
            df_filtered = df[(df['timestamp'].dt.date >= from_date) & (df['timestamp'].dt.date <= to_date)]
            time_label = f"{from_date} to {to_date}"
        elif filter_type == "Year":
            df['year'] = df['timestamp'].dt.year
            years = sorted(df['year'].dropna().unique())
            selected_year = st.sidebar.selectbox("Select Year", years)
            df_filtered = df[df['timestamp'].dt.year == selected_year]
            time_label = f"Year {selected_year}"
        else:
            df_filtered = df.copy()
            time_label = "All Time"

        df_filtered = df_filtered[df_filtered['common_name'] == selected_bird].copy()
        df_filtered.sort_values(by='timestamp', inplace=True)

        # Map
        if not df_filtered.empty:
            m = folium.Map(
                location=[df_filtered.iloc[0]['latitude'], df_filtered.iloc[0]['longitude']],
                zoom_start=6,
                tiles='Esri.WorldImagery'
            )

            location_counts = defaultdict(list)
            for _, row in df_filtered.iterrows():
                key = (round(row['latitude'], 3), round(row['longitude'], 3))
                location_counts[key].append(row['timestamp'])

            max_count = max(len(v) for v in location_counts.values())

            def encode_logo_to_base64(path):
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode()

            logo_base64 = encode_logo_to_base64("Icon.png")

            for (lat, lon), times in location_counts.items():
                count = len(times)
                latest_time = max(times)
                html_icon = f"""
                <div style=\"transform: translate(-50%, -50%)\">
                    <img src=\"data:image/png;base64,{logo_base64}\" width=\"30\" height=\"30\">
                </div>
                """
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.DivIcon(html=html_icon),
                    popup=folium.Popup(f"<b>Count:</b> {count}<br><b>Latest:</b> {latest_time.strftime('%Y-%m-%d %H:%M')}", max_width=250)
                ).add_to(m)

            st.subheader(f"📍 Predicted Locations of {selected_bird} ({time_label})")
            st_folium(m, width=1000, height=600)

            # TABLE: Show in descending order
            df_display = df_filtered.sort_values(by='timestamp', ascending=True)
            st.subheader("📊 Detection Table (Latest First)")
            st.dataframe(df_display[['timestamp', 'latitude', 'longitude', 'common_name']])
        else:
            st.warning("No data to display for selected filters.")
