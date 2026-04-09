import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- AUTOMATION: Sync Results from API ---
def sync_results(matches_df):
    api_key = st.secrets["CRICKET_API_KEY"]
    url = f"https://api.cricketdata.org/v1/currentMatches?apikey={api_key}"
    
    try:
        response = requests.get(url).json()
        if response['status'] != "success":
            return matches_df, False
        
        external_matches = response['data']
        updated = False
        
        for index, row in matches_df.iterrows():
            # Only look for matches that are missing a Winner
            if pd.isna(row['Winner']):
                # Find this match in the API data by matching team names
                for ex in external_matches:
                    if row['Team 1'] in ex['name'] and row['Team 2'] in ex['name']:
                        if ex['matchStarted'] and "won" in ex['status'].lower():
                            # Match is over! Update the data
                            matches_df.at[index, 'Winner'] = ex['status'].split(" won")[0]
                            # Note: Some APIs provide 'playerOfMatch' only in 'matchInfo' endpoint
                            # For now, we update the winner automatically
                            updated = True
        return matches_df, updated
    except:
        return matches_df, False

# 1. Load Data
matches_df = conn.read(worksheet="Matches", ttl="5m")
leaderboard_df = conn.read(worksheet="Leaderboard", ttl=0)
bets_df = conn.read(worksheet="Bets", ttl=0)

# 2. Run Sync (This happens silently in the background)
matches_df, needs_update = sync_results(matches_df)
if needs_update:
    conn.update(worksheet="Matches", data=matches_df)
    st.toast("Match results updated automatically!")

# --- SIDEBAR & MAIN PAGE CODE (Keep your existing betting/display code here) ---
# ... [Insert your previous sidebar and dataframe display code here] ...
