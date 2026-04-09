import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. THE FIX: CACHED DATA LOADING ---
# This prevents the app from hitting Google Sheets on every click
@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_data():
    try:
        matches = conn.read(worksheet="Matches", ttl="10m")
        leaderboard = conn.read(worksheet="Leaderboard", ttl="10m")
        players = conn.read(worksheet="Players", ttl="1h")
        return matches, leaderboard, players
    except Exception:
        return None, None, None

# Bets need a shorter cache so people see their submissions
@st.cache_data(ttl=2) 
def load_bets():
    return conn.read(worksheet="Bets", ttl=0)

matches_df_raw, leaderboard_df_raw, players_df_raw = load_data()
raw_bets = load_bets()

if matches_df_raw is None:
    st.error("Google API is overwhelmed. Please wait 1 minute and refresh.")
    st.stop()

# --- 2. DATA CLEANING ---
matches_df = matches_df_raw.fillna('')
leaderboard_df = leaderboard_df_raw.fillna('')
bets_df = raw_bets.dropna(subset=['Player', 'MatchID', 'Predicted Team'], how='all').fillna('')

# Normalize for matching
bets_df['MatchID'] = bets_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
bets_df['Player'] = bets_df['Player'].astype(str).str.strip()
matches_df['MatchID'] = matches_df['MatchID'].astype(str).str.split('.').str[0].str.strip()

player_list = sorted(players_df_raw['Name'].tolist()) if players_df_raw is not None else ["User 1", "User 2"]

# --- 3. SIDEBAR: User Portal ---
st.sidebar.header("User Portal")
current_player = st.sidebar.selectbox("Identify Yourself", ["S", "G", "T", "Shy", "Y", "D", "A"])

upcoming_df = matches_df[matches_df['Winner'] == ""].copy()

if not upcoming_df.empty:
    upcoming_df['display_name'] = "Match " + upcoming_df['MatchID'] + ": " + upcoming_df['Team 1'] + " vs " + upcoming_df['Team 2']
    selected_match_display = st.sidebar.selectbox("Select Match", upcoming_df['display_name'].tolist())
    
    match_id = str(upcoming_df[upcoming_df['display_name'] == selected_match_display]['MatchID'].values[0]).strip()
    match_info = matches_df[matches_df['MatchID'] == match_id].iloc[0]

    # Check Attempt Count
    user_history = bets_df[(bets_df['Player'] == current_player) & 
                           (bets_df['MatchID'] == match_id) & 
                           (bets_df['Predicted Team'] != "")]
    
    attempts = len(user_history)

    if attempts >= 2:
        final_bet = user_history.iloc[-1]
        st.sidebar.success(f"✅ {current_player}, bet locked.")
        st.sidebar.markdown(f"**Winner:** {final_bet['Predicted Team']}\n\n**Mult:** x{final_bet['Multiplier']}\n\n**MOTM:** {final_bet['Predicted MOTM']}")
        st.sidebar.warning("Max 2 attempts reached.")
    else:
        form_label = "Submit First Bet" if attempts == 0 else "Modify Bet (Final Chance)"
        with st.sidebar.form("bet_form"):
            st.write(f"**{form_label}**")
            pred_team = st.radio("Who wins?", [match_info['Team 1'], match_info['Team 2']])
            multiplier = st.selectbox("Multiplier", [1, 2, 3])
            pred_motm = st.selectbox("MOTM", player_list)
            submit = st.form_submit_button("Lock In Bet")

        if submit:
            new_row = pd.DataFrame([{"Player": str(current_player), "MatchID": str(match_id), "Predicted Team": str(pred_team), "Multiplier": str(multiplier), "Predicted MOTM": str(pred_motm)}])
            conn.update(worksheet="Bets", data=pd.concat([bets_df, new_row], ignore_index=True))
            st.cache_data.clear() # Clear cache so the new bet shows up immediately
            st.sidebar.success("Bet Saved!")
            time.sleep(1)
            st.rerun()
else:
    st.sidebar.info("No active matches.")

# --- 4. MAIN PAGE ---
col1, col2 = st.columns([1, 1.2])
with col1:
    st.subheader("🏆 Leaderboard")
    st.dataframe(leaderboard_df, hide_index=True)
with col2:
    st.subheader("📅 Schedule")
    st.dataframe(matches_df[['MatchID', 'Date', 'Team 1', 'Team 2', 'Winner']], hide_index=True)

st.subheader("📝 All Bets")
st.dataframe(bets_df[bets_df['Predicted Team'] != ""].tail(20), hide_index=True)
