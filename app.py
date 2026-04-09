import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. DATA LOADING ---
@st.cache_data(ttl=300)
def get_static_data():
    try:
        m_df = conn.read(worksheet="Matches", ttl="5m").fillna('')
        l_df = conn.read(worksheet="Leaderboard", ttl="5m").fillna('')
        p_df = conn.read(worksheet="Players", ttl="1h").fillna('')
        m_df['MatchID'] = m_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
        return m_df, l_df, p_df
    except Exception as e:
        st.error(f"Error loading Matches/Leaderboard: {e}")
        return None, None, None

def get_bets_live():
    # Define the structure we EXPECT
    required_cols = ["Player", "MatchID", "Predicted Team", "Multiplier", "Predicted MOTM", "EditCount", "Timestamp"]
    try:
        b_df = conn.read(worksheet="Bets", ttl=0).dropna(how='all').fillna('')
        
        # SELF-HEALING: If columns are missing in Google Sheets, add them here
        for col in required_cols:
            if col not in b_df.columns:
                b_df[col] = 0 if col == "EditCount" else ""
        
        if not b_df.empty:
            b_df['MatchID'] = b_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
            b_df['Player'] = b_df['Player'].astype(str).str.strip()
            b_df['EditCount'] = pd.to_numeric(b_df['EditCount'], errors='coerce').fillna(0).astype(int)
        
        return b_df[required_cols] # Force the correct order and columns
    except Exception:
        return pd.DataFrame(columns=required_cols)

matches_df, leaderboard_df, players_df = get_static_data()
bets_df = get_bets_live()

if matches_df is None:
    st.stop()

# --- 2. SIDEBAR: USER PORTAL ---
st.sidebar.header("User Portal")
current_user = st.sidebar.selectbox("Identify Yourself", ["S", "G", "T", "Shy", "Y", "D", "A"])

# Filter active matches
active_matches = matches_df[matches_df['Winner'].astype(str).str.strip() == ""].copy()

if not active_matches.empty:
    active_matches['display'] = "Match " + active_matches['MatchID'] + ": " + active_matches['Team 1'] + " vs " + active_matches['Team 2']
    selected_match = st.sidebar.selectbox("Select Match", active_matches['display'].tolist())
    
    m_id = str(active_matches[active_matches['display'] == selected_match]['MatchID'].values[0]).strip()
    m_info = active_matches[active_matches['MatchID'] == m_id].iloc[0]

    # Find existing bet
    mask = (bets_df['Player'] == current_user) & (bets_df['MatchID'] == m_id)
    user_bet = bets_df[mask]

    # Check edit status
    current_edits = int(user_bet['EditCount'].values[0]) if not user_bet.empty else 0

    if current_edits >= 2:
        locked_data = user_bet.iloc[0]
        st.sidebar.success(f"✅ Bet Finalized for {current_user}")
        st.sidebar.markdown(f"""
        **Locked Prediction:**
        - **Winner:** {locked_data['Predicted Team']}
        - **Multiplier:** x{locked_data['Multiplier']}
        - **MOTM:** {locked_data['Predicted MOTM']}
        """)
        st.sidebar.warning("No more changes allowed.")
    else:
        with st.sidebar.form("bet_form"):
            label = "First Bet" if current_edits == 0 else "Final Modification"
            st.subheader(label)
            p_team = st.radio("Who wins?", [m_info['Team 1'], m_info['Team 2']])
            p_mult = st.select_slider("Multiplier", options=[1, 2, 3])
            p_names = sorted(players_df['Name'].tolist()) if not players_df.empty else ["N/A"]
            p_motm = st.selectbox("MOTM", p_names)
            submitted = st.form_submit_button("Lock In Bet")

        if submitted:
            # Re-fetch live to ensure no one else is overwritten
            live_bets = get_bets_live()
            now_ts = datetime.now().strftime("%d-%m %H:%M")
            
            row_mask = (live_bets['Player'] == current_user) & (live_bets['MatchID'] == m_id)
            
            if not live_bets[row_mask].empty:
                # UPDATE EXISTING ROW
                idx = live_bets[row_mask].index[0]
                live_bets.at[idx, 'Predicted Team'] = p_team
                live_bets.at[idx, 'Multiplier'] = p_mult
                live_bets.at[idx, 'Predicted MOTM'] = p_motm
                live_bets.at[idx, 'Timestamp'] = now_ts
                live_bets.at[idx, 'EditCount'] = 2 
            else:
                # INSERT NEW ROW
                new_row = pd.DataFrame([{
                    "Player": current_user, "MatchID": m_id, 
                    "Predicted Team": p_team, "Multiplier": p_mult, 
                    "Predicted MOTM": p_motm, "EditCount": 1, "Timestamp": now_ts
                }])
                live_bets = pd.concat([live_bets, new_row], ignore_index=True)
            
            conn.update(worksheet="Bets", data=live_bets)
            st.cache_data.clear()
            st.sidebar.balloons()
            st.rerun()
else:
    st.sidebar.info("No active matches found.")

# --- 3. MAIN DASHBOARD ---
t1, t2 = st.tabs(["🏆 Standings", "📝 All Bets"])
with t1:
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.subheader("Leaderboard")
        st.table(leaderboard_df)
    with col2:
        st.subheader("Upcoming")
        st.dataframe(matches_df[['MatchID', 'Date', 'Team 1', 'Team 2']].head(10), hide_index=True)

with t2:
    st.subheader("Global Bets")
    if not bets_df.empty:
        display_cols = ["Player", "MatchID", "Predicted Team", "Multiplier", "Predicted MOTM", "Timestamp"]
        valid_bets = bets_df[bets_df['Predicted Team'] != ""]
        st.dataframe(valid_bets[display_cols].sort_index(ascending=False), hide_index=True, use_container_width=True)
    else:
        st.info("No bets placed yet.")
