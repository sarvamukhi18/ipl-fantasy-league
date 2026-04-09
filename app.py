import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# Read data
matches_df = conn.read(worksheet="Matches", ttl="5m")
leaderboard_df = conn.read(worksheet="Leaderboard", ttl=0)
bets_df = conn.read(worksheet="Bets", ttl=0)

# --- SIDEBAR: Submit a Bet ---
st.sidebar.header("Submit Your Prediction")
with st.sidebar.form("bet_form"):
    # 1. Searchable Player List
    player = st.selectbox("Who are you?", ["S", "G", "T", "Shy", "Y", "D", "A"])
    
    # 2. Match Detection Logic
    upcoming_df = matches_df[matches_df['Winner'].isna()].copy()
    
    # Create a nice label for the dropdown
    upcoming_df['display_name'] = "Match " + upcoming_df['MatchID'].astype(str) + ": " + upcoming_df['Team 1'] + " vs " + upcoming_df['Team 2']
    
    # Auto-select match based on today's date
    today_str = datetime.now().strftime("%d-%m-%Y")
    todays_match_row = upcoming_df[upcoming_df['Date'] == today_str]
    
    default_index = 0
    if not todays_match_row.empty:
        default_index = upcoming_df.index.get_loc(todays_match_row.index[0])

    selected_display = st.selectbox("Select Match", upcoming_df['display_name'].tolist(), index=default_index)
    
    # Get the actual MatchID from the selection
    match_id = upcoming_df[upcoming_df['display_name'] == selected_display]['MatchID'].values[0]
    match_info = matches_df[matches_df['MatchID'] == match_id].iloc[0]
    
    # 3. Predictions
    pred_team = st.radio("Who will win?", [match_info['Team 1'], match_info['Team 2']])
    
    # 4. Limited Multiplier
    multiplier = st.selectbox("Multiplier", [1, 2, 3])
    
    pred_motm = st.text_input("Predicted MOTM")
    
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
