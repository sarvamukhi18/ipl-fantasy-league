import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# 1. Load and Clean Data
try:
    matches_df = conn.read(worksheet="Matches", ttl="5m").fillna('')
    leaderboard_df = conn.read(worksheet="Leaderboard", ttl=0).fillna('')
    
    # Load bets and drop completely empty rows
    raw_bets = conn.read(worksheet="Bets", ttl=0)
    # Ensure we only count rows that have actual data
    bets_df = raw_bets.dropna(subset=['Player', 'MatchID', 'Predicted Team'], how='all').fillna('')

    # Normalize data for matching
    bets_df['MatchID'] = bets_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
    bets_df['Player'] = bets_df['Player'].astype(str).str.strip()
    matches_df['MatchID'] = matches_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
except Exception as e:
    st.error(f"Data Load Error: {e}")
    st.stop()

# 2. Player List
try:
    all_players_df = conn.read(worksheet="Players", ttl="1h")
    player_list = sorted(all_players_df['Name'].tolist())
except:
    player_list = ["Virat Kohli", "MS Dhoni", "Rohit Sharma", "Shubman Gill", "Rashid Khan", "Other"]

# --- SIDEBAR: User Portal ---
st.sidebar.header("User Portal")
current_player = st.sidebar.selectbox("Identify Yourself", ["S", "G", "T", "Shy", "Y", "D", "A"])

# Filter for active matches (Winner column is empty)
upcoming_df = matches_df[matches_df['Winner'] == ""].copy()

if not upcoming_df.empty:
    upcoming_df['display_name'] = "Match " + upcoming_df['MatchID'] + ": " + upcoming_df['Team 1'] + " vs " + upcoming_df['Team 2']
    selected_match_display = st.sidebar.selectbox("Select Match", upcoming_df['display_name'].tolist())
    
    match_id = str(upcoming_df[upcoming_df['display_name'] == selected_match_display]['MatchID'].values[0]).strip()
    match_info = matches_df[matches_df['MatchID'] == match_id].iloc[0]

    # --- CHECK ATTEMPT COUNT ---
    # Only rows with a real Predicted Team count as an attempt
    user_history = bets_df[(bets_df['Player'] == current_player) & 
                           (bets_df['MatchID'] == match_id) & 
                           (bets_df['Predicted Team'] != "")]
    
    attempts = len(user_history)

    if attempts >= 2:
        # PERMANENTLY LOCKED after 2 tries
        final_bet = user_history.iloc[-1]
        st.sidebar.success(f"✅ {current_player}, your final bet is locked.")
        st.sidebar.markdown(f"""
        **Final Prediction:**
        - **Winner:** {final_bet['Predicted Team']}
        - **Multiplier:** x{final_bet['Multiplier']}
        - **MOTM:** {final_bet['Predicted MOTM']}
        """)
        st.sidebar.warning("No more changes allowed (Max 2 attempts reached).")
    else:
        # ALLOW SUBMISSION (Attempt 1 or 2)
        if attempts == 0:
            form_label = "Submit First Bet"
        else:
            form_label = "Modify My Bet (Last Chance!)"
            st.sidebar.info("You've placed 1 bet. This next submission will lock it permanently.")
        
        with st.sidebar.form("bet_form"):
            st.write(f"**{form_label}** for {current_player}")
            pred_team = st.radio("Who wins?", [match_info['Team 1'], match_info['Team 2']])
            multiplier = st.selectbox("Multiplier", [1, 2, 3])
            pred_motm = st.selectbox("Man of the Match", player_list)
            submit = st.form_submit_button("Lock In Bet")

        if submit:
            new_row = pd.DataFrame([{
                "Player": str(current_player), 
                "MatchID": str(match_id), 
                "Predicted Team": str(pred_team),
                "Multiplier": str(multiplier), 
                "Predicted MOTM": str(pred_motm)
            }])
            updated_bets = pd.concat([bets_df, new_row], ignore_index=True)
            conn.update(worksheet="Bets", data=updated_bets)
            st.sidebar.balloons()
            st.sidebar.success("Bet Saved!")
            time.sleep(1)
            st.rerun()
else:
    st.sidebar.info("No active matches.")

# --- MAIN PAGE ---
col1, col2 = st.columns([1, 1.2])
with col1:
    st.subheader("🏆 Leaderboard")
    st.dataframe(leaderboard_df, hide_index=True, use_container_width=True)
with col2:
    st.subheader("📅 Schedule")
    st.dataframe(matches_df[['MatchID', 'Date', 'Team 1', 'Team 2', 'Winner']], hide_index=True)

st.subheader("📝 All Bets")
# Filter out any ghost rows from the display table
valid_display_df = bets_df[bets_df['Predicted Team'] != ""]
st.dataframe(valid_display_df.tail(20), use_container_width=True, hide_index=True)
