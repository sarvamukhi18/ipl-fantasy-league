import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Set up page title
st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

# Create connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Read data from the sheets
# We use ttl=0 for the Leaderboard and Bets so updates show up immediately
matches_df = conn.read(worksheet="Matches", ttl="10m")
leaderboard_df = conn.read(worksheet="Leaderboard", ttl=0)
bets_df = conn.read(worksheet="Bets", ttl=0)

# --- SIDEBAR: Submit a Bet ---
st.sidebar.header("Submit Your Prediction")
with st.sidebar.form("bet_form"):
    player = st.sidebar.selectbox("Who are you?", ["S", "G", "T", "Shy", "Y", "D", "A"])
    
    # Only show matches that haven't been played yet (Winner is blank)
    upcoming_matches = matches_df[matches_df['Winner'].isna()]['MatchID'].tolist()
    match_id = st.selectbox("Select Match ID", upcoming_matches)
    
    # Get team names for the selected match
    if match_id:
        match_info = matches_df[matches_df['MatchID'] == match_id].iloc[0]
        teams = [match_info['Team 1'], match_info['Team 2']]
        pred_team = st.radio("Who will win?", teams)
    
    multiplier = st.number_input("Multiplier (1-5)", min_value=1, max_value=5, value=1)
    pred_motm = st.text_input("Predicted MOTM")
    
    submit = st.form_submit_button("Submit Bet")

if submit:
    # Create a new row for the 'Bets' sheet
    new_bet = pd.DataFrame([{
        "Player": player,
        "MatchID": match_id,
        "Predicted Team": pred_team,
        "Multiplier": multiplier,
        "Predicted MOTM": pred_motm
    }])
    
    # Combine with old bets and update the sheet
    updated_bets = pd.concat([bets_df, new_bet], ignore_index=True)
    conn.update(worksheet="Bets", data=updated_bets)
    st.sidebar.success("Bet Submitted! Refresh the page to see updates.")
    st.rerun()

# --- MAIN PAGE: Displaying the Data ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("🏆 Live Leaderboard")
    # Show the leaderboard tab where your Excel formulas are doing the math
    st.dataframe(leaderboard_df, hide_index=True)

with col2:
    st.subheader("📅 Schedule & Results")
    st.dataframe(matches_df, hide_index=True)

st.subheader("📝 Recent Bets")
st.dataframe(bets_df.tail(10), use_container_width=True)
