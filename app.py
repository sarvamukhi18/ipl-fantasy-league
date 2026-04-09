import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import requests
import time

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- AUTOMATION: Sync Results from API ---
def sync_results(matches_df):
    try:
        api_key = st.secrets["CRICKET_API_KEY"]
        url = f"https://api.cricketdata.org/v1/currentMatches?apikey={api_key}"
        response = requests.get(url).json()
        if response.get('status') != "success":
            return matches_df, False
        
        external_matches = response.get('data', [])
        updated = False
        for index, row in matches_df.iterrows():
            if pd.isna(row['Winner']) or str(row['Winner']).strip() == "":
                for ex in external_matches:
                    if row['Team 1'] in ex['name'] and row['Team 2'] in ex['name']:
                        if ex.get('matchStarted') and "won" in ex.get('status', '').lower():
                            winner_name = ex['status'].split(" won")[0].strip()
                            matches_df.at[index, 'Winner'] = winner_name
                            updated = True
        return matches_df, updated
    except Exception:
        return matches_df, False

# 1. Load Data
try:
    matches_df = conn.read(worksheet="Matches", ttl="5m")
    leaderboard_df = conn.read(worksheet="Leaderboard", ttl=0).fillna('')
    # Load and clean bets
    raw_bets = conn.read(worksheet="Bets", ttl=0)
    bets_df = raw_bets.fillna('')
    
    # Crucial: Ensure columns are strings and stripped of hidden spaces
    bets_df['MatchID'] = bets_df['MatchID'].astype(str).str.strip()
    bets_df['Player'] = bets_df['Player'].astype(str).str.strip()
except Exception:
    st.error("Connection busy. Please refresh.")
    st.stop()

# 2. Sync Results
matches_df, needs_update = sync_results(matches_df)
if needs_update:
    conn.update(worksheet="Matches", data=matches_df)
    st.toast("Results updated!", icon="✅")

# 3. Player List
try:
    all_players_df = conn.read(worksheet="Players", ttl="1h")
    player_list = sorted(all_players_df['Name'].tolist())
except:
    player_list = ["Virat Kohli", "MS Dhoni", "Rohit Sharma", "Shubman Gill", "Rashid Khan", "Other"]

# --- SIDEBAR: Submit a Bet ---
st.sidebar.header("User Portal")
current_player = st.sidebar.selectbox("Identify Yourself", ["S", "G", "T", "Shy", "Y", "D", "A"])

# Filter for matches that haven't ended
upcoming_df = matches_df[matches_df['Winner'].isna() | (matches_df['Winner'] == "")].copy()

if not upcoming_df.empty:
    upcoming_df['display_name'] = "Match " + upcoming_df['MatchID'].astype(str) + ": " + upcoming_df['Team 1'] + " vs " + upcoming_df['Team 2']
    
    today_str = datetime.now().strftime("%d-%m-%Y")
    todays_match_row = upcoming_df[upcoming_df['Date'] == today_str]
    default_index = 0
    if not todays_match_row.empty:
        default_index = upcoming_df.index.get_loc(todays_match_row.index[0])

    selected_match_display = st.sidebar.selectbox("Select Match", upcoming_df['display_name'].tolist(), index=default_index)
    
    # Get MatchID as clean string
    match_id = str(upcoming_df[upcoming_df['display_name'] == selected_match_display]['MatchID'].values[0]).strip()
    match_info = matches_df[matches_df['MatchID'].astype(str).str.strip() == match_id].iloc[0]

    # --- THE FIX: Precise Filtering for Current Player + Selected Match ---
    user_has_bet = bets_df[(bets_df['Player'] == current_player) & (bets_df['MatchID'] == match_id)]

    if not user_has_bet.empty:
        bet_data = user_has_bet.iloc[0]
        st.sidebar.success(f"✅ {current_player}, your bet is locked.")
        st.sidebar.markdown(f"""
        **Your Prediction:**
        * **Winner:** {bet_data['Predicted Team']}
        * **Multiplier:** x{bet_data['Multiplier']}
        * **MOTM:** {bet_data['Predicted MOTM']}
        """)
    else:
        with st.sidebar.form("bet_form", clear_on_submit=True):
            st.write(f"New Bet for {current_player}")
            st.write(f"**{match_info['Team 1']} vs {match_info['Team 2']}**")
            pred_team = st.radio("Pick Winner", [match_info['Team 1'], match_info['Team 2']])
            multiplier = st.selectbox("Multiplier", [1, 2, 3])
            pred_motm = st.selectbox("Man of the Match", player_list)
            submit = st.form_submit_button("Submit Prediction")

        if submit:
            new_row = {
                "Player": str(current_player), 
                "MatchID": str(match_id), 
                "Predicted Team": str(pred_team),
                "Multiplier": int(multiplier), 
                "Predicted MOTM": str(pred_motm)
            }
            new_bet_df = pd.DataFrame([new_row])
            updated_bets = pd.concat([bets_df, new_bet_df], ignore_index=True)
            
            conn.update(worksheet="Bets", data=updated_bets)
            st.sidebar.balloons()
            st.sidebar.success("Bet Placed!")
            time.sleep(1.5)
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

st.subheader("📝 Recent Activity")
st.dataframe(bets_df.tail(15), use_container_width=True, hide_index=True)
