import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

# Initialize connection once
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SPEED FIX: LONG-TERM CACHING ---
@st.cache_data(ttl=1200) # Cache for 20 minutes to save speed
def load_static_data():
    try:
        m_df = conn.read(worksheet="Matches", ttl="20m").fillna('')
        l_df = conn.read(worksheet="Leaderboard", ttl="20m").fillna('')
        p_df = conn.read(worksheet="Players", ttl="1h").fillna('')
        
        # Clean MatchIDs immediately
        m_df['MatchID'] = m_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
        return m_df, l_df, p_df
    except:
        return None, None, None

@st.cache_data(ttl=5) # Short cache for bets so they feel "live"
def load_bets_data():
    try:
        b_df = conn.read(worksheet="Bets", ttl=0)
        b_df = b_df.dropna(subset=['Player', 'MatchID'], how='all').fillna('')
        b_df['MatchID'] = b_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
        b_df['Player'] = b_df['Player'].astype(str).str.strip()
        return b_df
    except:
        return pd.DataFrame()

# Load data into the app
matches_df, leaderboard_df, players_df = load_static_data()
bets_df = load_bets_data()

if matches_df is None:
    st.warning("🔄 Syncing with Google... please wait a moment.")
    st.stop()

# --- SIDEBAR: User Portal ---
st.sidebar.header("User Portal")
current_player = st.sidebar.selectbox("Who are you?", ["S", "G", "T", "Shy", "Y", "D", "A"])

# Filter for active matches
upcoming_df = matches_df[matches_df['Winner'] == ""].copy()

if not upcoming_df.empty:
    upcoming_df['display_name'] = "Match " + upcoming_df['MatchID'] + ": " + upcoming_df['Team 1'] + " vs " + upcoming_df['Team 2']
    selected_match = st.sidebar.selectbox("Select Match", upcoming_df['display_name'].tolist())
    
    m_id = str(upcoming_df[upcoming_df['display_name'] == selected_match]['MatchID'].values[0]).strip()
    m_info = matches_df[matches_df['MatchID'] == m_id].iloc[0]

    # Check History
    user_history = bets_df[(bets_df['Player'] == current_player) & (bets_df['MatchID'] == m_id) & (bets_df['Predicted Team'] != "")]
    attempts = len(user_history)

    if attempts >= 2:
        final = user_history.iloc[-1]
        st.sidebar.success(f"✅ Bet Locked")
        st.sidebar.write(f"**Winner:** {final['Predicted Team']} | **Mult:** x{final['Multiplier']}")
    else:
        with st.sidebar.form("bet_form", clear_on_submit=True):
            st.write("Edit 2/2" if attempts == 1 else "Submit Bet")
            p_team = st.radio("Winner?", [m_info['Team 1'], m_info['Team 2']])
            mult = st.selectbox("Multiplier", [1, 2, 3])
            # Use player names from the 'Players' sheet if available
            p_names = sorted(players_df['Name'].tolist()) if not players_df.empty else ["N/A"]
            p_motm = st.selectbox("MOTM", p_names)
            submit = st.form_submit_button("Lock In")

        if submit:
            new_row = pd.DataFrame([{"Player": current_player, "MatchID": m_id, "Predicted Team": p_team, "Multiplier": mult, "Predicted MOTM": p_motm}])
            conn.update(worksheet="Bets", data=pd.concat([bets_df, new_row], ignore_index=True))
            st.cache_data.clear() # Reset cache so data updates
            st.sidebar.success("Saved!")
            time.sleep(1)
            st.rerun()

# --- MAIN PAGE (Simplified for Speed) ---
c1, c2 = st.columns([1, 1.2])
with c1:
    st.subheader("🏆 Leaderboard")
    st.table(leaderboard_df) # st.table is faster than st.dataframe for small data
with c2:
    st.subheader("📅 Schedule")
    st.dataframe(matches_df[['MatchID', 'Date', 'Team 1', 'Team 2', 'Winner']].head(15), hide_index=True)

st.subheader("📝 Recent Bets")
st.dataframe(bets_df[bets_df['Predicted Team'] != ""].tail(10), hide_index=True)
