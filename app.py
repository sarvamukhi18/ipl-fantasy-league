import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# 1. Read data
matches_df = conn.read(worksheet="Matches", ttl="5m")
leaderboard_df = conn.read(worksheet="Leaderboard", ttl=0)
bets_df = conn.read(worksheet="Bets", ttl=0)

# Try to load a player list for the MOTM search
try:
    all_players_df = conn.read(worksheet="Players", ttl="1h")
    player_list = sorted(all_players_df['Name'].tolist())
except:
    # Fallback if you haven't created a 'Players' tab yet
    player_list = ["Virat Kohli", "MS Dhoni", "Rohit Sharma", "Shubman Gill", "Rashid Khan", "Other"]

# --- SIDEBAR: Submit a Bet ---
st.sidebar.header("Submit Your Prediction")

# User Selection
player = st.sidebar.selectbox("Who are you?", ["S", "G", "T", "Shy", "Y", "D", "A"])

# Match Selection
upcoming_df = matches_df[matches_df['Winner'].isna()].copy()
upcoming_df['display_name'] = "Match " + upcoming_df['MatchID'].astype(str) + ": " + upcoming_df['Team 1'] + " vs " + upcoming_df['Team 2']

today_str = datetime.now().strftime("%d-%m-%Y")
todays_match_row = upcoming_df[upcoming_df['Date'] == today_str]

default_index = 0
if not todays_match_row.empty:
    default_index = upcoming_df.index.get_loc(todays_match_row.index[0])

selected_display = st.sidebar.selectbox("Select Match", upcoming_df['display_name'].tolist(), index=default_index)

match_id = upcoming_df[upcoming_df['display_name'] == selected_display]['MatchID'].values[0]
match_info = matches_df[matches_df['MatchID'] == match_id].iloc[0]

# --- BETTING FORM ---
with st.sidebar.form("bet_form"):
    pred_team = st.radio(f"Who will win?", [match_info['Team 1'], match_info['Team 2']])
    
    multiplier = st.selectbox("Multiplier", [1, 2, 3])
    
    # NEW: Searchable MOTM List
    pred_motm = st.selectbox("Predicted MOTM (Type to search)", player_list)
    
    submit = st.form_submit_button("Submit Bet")

if submit:
    new_bet = pd.DataFrame([{
        "Player": player,
        "MatchID": match_id,
        "Predicted Team": pred_team,
        "Multiplier": multiplier,
        "Predicted MOTM": pred_motm
    }])
    
    updated_bets = pd.concat([bets_df, new_bet], ignore_index=True)
    conn.update(worksheet="Bets", data=updated_bets)
    st.sidebar.success("Bet Submitted!")
    st.rerun()

# --- MAIN PAGE ---
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("🏆 Live Leaderboard")
    st.dataframe(leaderboard_df, hide_index=True, use_container_width=True)

with col2:
    st.subheader("📅 Schedule & Results")
    st.dataframe(matches_df[['MatchID', 'Date', 'Team 1', 'Team 2', 'Winner']], hide_index=True)

st.subheader("📝 Recent Bets")
st.dataframe(bets_df.tail(10), use_container_width=True, hide_index=True)
