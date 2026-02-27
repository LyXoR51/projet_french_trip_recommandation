#####   LIBRARY  #####
from sqlalchemy import create_engine, text
import streamlit as st
from datetime import datetime
import pandas as pd
import os
import plotly.express as px
import requests

st.set_page_config(layout="wide")

#####   DATA & VARIABLE  #####
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE")
ENGINE = create_engine(POSTGRES_DATABASE, echo=True)
TABLE_CITIES = 'trip_reco_cities'
TABLE_HOTELS = 'trip_reco_hotels'
TABLE_WEATHERS = 'trip_reco_weathers'
OPENWEATHERMAP_URL = os.getenv("OPENWEATHERMAP_URL")
OPENWEATHERMAP_API_KEY= os.getenv("OPENWEATHERMAP_API_KEY")


##### FUNCTIONS #####
def update_weather():
    with ENGINE.begin() as conn:
        # Clean table first
        conn.execute(text(f"TRUNCATE TABLE {TABLE_WEATHERS}"))

        stmt = text(f"SELECT * FROM {TABLE_CITIES}")
        result = conn.execute(stmt)
        df_cities = pd.DataFrame(result.fetchall(), columns=result.keys())

    df_weather = pd.DataFrame()

    for city_id in df_cities['city_id']:
        lat = df_cities.loc[df_cities['city_id']==city_id, 'latitude'].values[0]
        lon = df_cities.loc[df_cities['city_id']==city_id, 'longitude'].values[0]

        params = {'lat': lat, 'lon': lon, 'units':'metric', 'appid': OPENWEATHERMAP_API_KEY}
        req = requests.get(OPENWEATHERMAP_URL, params=params).json()

        for dt in req['list']:
            data = {
                'city_id': city_id,
                'datetime': datetime.fromtimestamp(dt['dt']),
                'temp_min': dt['main']['temp_min'],
                'temp_max': dt['main']['temp_max'],
                'temp_feels_like': dt['main']['feels_like'],
                'sky': dt['weather'][0]['description'],
                'updated_at': int(datetime.timestamp(datetime.now())*1000)
            }
            df_weather = pd.concat([df_weather, pd.DataFrame([data])], ignore_index=True)

    df_weather.reset_index(drop=True, inplace=True)
    df_weather['weather_id'] = df_weather.index + 1

    df_weather.to_sql(TABLE_WEATHERS, ENGINE, if_exists='append', index=False)

    



##### APP #####
st.markdown("""
# 🇫🇷 French Trip Recommendation

Plan your next French adventure with our **recommendation engine**!  
This app uses weather forecasts and hotel data to suggest the best cities to visit.

Here's what you'll find:

- **🌤️ Top 5 Cities**: Cities with perfect weather (no rain & pleasant temperature) over the next 5 days.  
- **🏨 Top Hotels**: The best hotels in your chosen city.  
- **🗺️ All Cities & Hotels**: Explore our full database on interactive maps.  
- **🏗️ Architecture & Workflow**: How the app works under the hood.
""")


with st.expander("**Weather & Top Recommendations**", expanded=True):
    with ENGINE.connect() as conn:
        stmt = text(f"""
            SELECT updated_at, datetime
            FROM {TABLE_WEATHERS}
            ORDER BY datetime DESC
            LIMIT 1
        """)
        result = conn.execute(stmt)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        last_update = pd.to_datetime(df['updated_at'], unit='ms')[0]

    st.markdown(f"""
    Discover the **top 5 French cities** with the best weather over the next 5 days ({df['datetime'][0]}), and explore the **top 20 hotels** in the best city.  
    You can also update the weather data manually using the button below.
    """)

    #### Create two columns
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 5 cities", divider=True)   
        with ENGINE.connect() as conn:
        #looking for the best AVG temp during all the trip, and NO rain !
            stmt = text(f"""
                SELECT w.city_id, c.name, AVG(w.temp_feels_like) AS Temp_feels_like, c.latitude, c.longitude
                FROM {TABLE_WEATHERS} AS w
                JOIN {TABLE_CITIES} AS c ON w.city_id = c.city_id
                WHERE EXTRACT(HOUR FROM w.datetime) BETWEEN 6 AND 20
                GROUP BY w.city_id, c.name, c.latitude, c.longitude
                HAVING COUNT(CASE WHEN w.sky LIKE '%rain%' THEN 1 END) < 5 
                ORDER BY AVG(w.temp_feels_like) DESC
                LIMIT 5
            """)
            result = conn.execute(stmt)
            Top_five_city = pd.DataFrame(result)
            Best_choice = Top_five_city["city_id"][0]
            fig = px.scatter_mapbox(Top_five_city, lat="latitude", lon="longitude", zoom=3, mapbox_style="carto-positron",hover_name='name', size='temp_feels_like', color='temp_feels_like', color_continuous_scale='Bluered')
            st.plotly_chart(fig)

    with col2:
        st.subheader("Best Hotels in Our Top Destination", divider=True)   
        with ENGINE.connect() as conn:
            stmt = text(f"""
            SELECT *
            FROM {TABLE_HOTELS}
            WHERE city_id = {Best_choice}
            ORDER BY rating DESC
            LIMIT 20
        """)
            result = conn.execute(stmt)
            best_hostel = pd.DataFrame(result)
            fig = px.scatter_mapbox(best_hostel, lat="latitude", lon="longitude", zoom=11, mapbox_style="carto-positron",hover_name='name', color='rating', color_continuous_scale='Bluered')  
            st.plotly_chart(fig)

    st.write(f"Last update : {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
    if st.button("Update Weather"):
        update_weather()
        st.rerun()
        st.success("Weather data updated successfully!")
    


with st.expander("**Cities and hotels**"):
    st.markdown("""
    Explore our curated selection of **35 top French cities** and their **hotels** on an interactive map.  
    Use the selector below to switch between cities and hotels.
    """)

    option = st.radio("Select data to display:", ["Cities", "Hotels"])

    with ENGINE.connect() as conn:
        if option == "Cities":
            stmt = text(f"SELECT name, latitude, longitude FROM {TABLE_CITIES}")
            result = conn.execute(stmt)
            df_cities = pd.DataFrame(result.fetchall(), columns=result.keys())

            if not df_cities.empty:
                fig_map = px.scatter_mapbox(
                    df_cities,
                    lat="latitude",
                    lon="longitude",
                    hover_name="name",
                    zoom=4,
                    mapbox_style="carto-positron",
                    color_discrete_sequence=["blue"],
                    size_max=10
                )
                st.plotly_chart(fig_map)
            else:
                st.warning("No cities found in the database.")

        else:  
            stmt = text(f"SELECT name, latitude, longitude, rating FROM {TABLE_HOTELS}")
            result = conn.execute(stmt)
            df_hotels = pd.DataFrame(result.fetchall(), columns=result.keys())

            if not df_hotels.empty:
                fig_map = px.scatter_mapbox(
                    df_hotels,
                    lat="latitude",
                    lon="longitude",
                    hover_name="name",
                    color="rating",
                    color_continuous_scale="Bluered",
                    zoom=4,
                    mapbox_style="carto-positron",
                    size_max=10
                )
                st.plotly_chart(fig_map)
            else:
                st.warning("No hotels found in the database.")


with st.expander("**Architecture & Workflow**"):
    st.markdown("""
This project follows a complete **data pipeline lifecycle** — from data collection to user-facing recommendations in Streamlit.
""")

    st.image(os.path.join(os.path.dirname(__file__), "images", "architecture.png"))

    st.markdown("""

#### 1. Cities & GPS Collection
- A curated list of 35 French cities was created.  
- GPS coordinates for each city are collected using the **Nominatim API**.  
- City data (name, latitude, longitude) is stored in a **SQL database**.

#### 2. Hotels 
- Hotel information is loaded from CSV files.  
- Data undergoes **ETL processing** (cleaning, transformations).  
- Hotels data is stored in the **SQL database** linked to city IDs.

#### 3. Weather Collection
- For each city GPS, weather forecasts are retrieved via the **OpenWeather API**.  
- Forecasts include temperature, "feels like" temperature, and precipitation for the next 5 days.  
- Weather data is loaded into the **SQL database** for query and recommendation purposes, linked to city IDs.

#### 4. Streamlit User Interface
- **Streamlit app** (hosted on Hugging Face Spaces) provides an interactive dashboard:
    - Top 5 cities based on pleasant temperature and no rain.
    - Top 20 hotels for the selected city.
    - Map view of all 35 curated cities or hotels.
    - Manual weather update via API call.""")