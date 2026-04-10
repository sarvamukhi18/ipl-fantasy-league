import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time as dt_time
import pytz
import time

# --- CONFIG ---
st.set_page_config(page_title="IPL Betting Hub", layout="wide")
ist = pytz.timezone('Asia/Kolkata')

# --- UI STYLING ---
st.markdown("""
    <style>
    .match-card { border: 1px solid #ddd; padding: 15px; border-radius: 10px; margin-bottom: 10px; background-color: white; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. DATA LOADING (Capped to prevent 429 Errors) ---

@st.cache_data(ttl=86400) # Refreshes once every 24 hours
def get_leaderboard():
    return conn.read(worksheet="Leaderboard", ttl="24h").fillna(0)

@st.cache_data(ttl=600)
def get_static_data():
    m_df = conn.read(worksheet="Matches", ttl="10m").fillna('')
    p_df = conn.read(worksheet="Players", ttl="1h").fillna('')
    # Force MatchID to string and strip spaces to ensure matching works
    m_df['MatchID'] = m_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
    return m_df, p_df

def get_bets_live():
    try:
        b_df = conn.read(worksheet="Bets", ttl=0).dropna(how='all').fillna('')
        if not b_df.empty:
            # Clean data for precise matching with your placeholders
            b_df['MatchID'] = b_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
            b_df['Player'] = b_df['Player'].astype(str).str.strip()
            if 'EditCount' not in b_df.columns: b_df['EditCount'] = 0
            b_df['EditCount'] = pd.to_numeric(b_df['EditCount'], errors='coerce').fillna(0).astype(int)
        return b_df
    except:
        return pd.DataFrame(columns=["Player", "MatchID", "Predicted Team", "Multiplier", "Predicted MOTM", "EditCount", "Timestamp"])

matches_df, players_df = get_static_data()
leaderboard_df = get_leaderboard()
bets_df = get_bets_live()

# --- 2. MAIN DASHBOARD ---
col_main, col_leader = st.columns([2, 1])

with col_leader:
    st.subheader("🏆 Leaderboard")
    st.table(leaderboard_df)
    st.caption("Updated daily at 12:00 AM IST.")

with col_main:
    player_list = ["S", "G", "T", "Shy", "Y", "D", "A"]
    current_user = st.selectbox("Identify Yourself", player_list)
    
    # Get current IST date and time
    now_ist = datetime.now(ist)
    today_date = now_ist.strftime("%Y-%m-%d")
    
    # Filter matches for today
    todays_matches = matches_df[matches_df['Date'] == today_date].sort_values('MatchID')
    
    if todays_matches.empty:
        st.info("No matches scheduled for today.")
    else:
        st.subheader(f"Matches for Today ({now_ist.strftime('%d %b')})")
        
        for i, (idx, match) in enumerate(todays_matches.iterrows()):
            m_id = match['MatchID']
            
            # --- LOCKOUT LOGIC ---
            # If 2 matches today, 1st is 3:30 PM, 2nd is 7:30 PM. Otherwise 7:30 PM.
            if len(todays_matches) > 1:
                match_time = dt_time(15, 30) if i == 0 else dt_time(19, 30)
            else:
                match_time = dt_time(19, 30)
            
            is_locked = now_ist.time() >= match_time
            
            # Check for existing bet in your sheet (placeholder or previous entry)
            user_bet_row = bets_df[(bets_df['Player'] == current_user) & (bets_df['MatchID'] == m_id)]
            current_edits = int(user_bet_row['EditCount'].values[0]) if not user_bet_row.empty else 0
            
            with st.container():
                st.markdown(f"### Match {m_id}: {match['Team 1']} vs {match['Team 2']}")
                st.write(f"🕒 **Lockout Time:** {match_time.strftime('%I:%M %p')} IST")
                
                if is_locked:
                    st.error("🚫 Betting is closed for this match.")
                    if not user_bet_row.empty and user_bet_row.iloc[0]['Predicted Team'] != "":
                        st.info(f"Your Bet: {user_bet_row.iloc[0]['Predicted Team']} (x{user_bet_row.iloc[0]['Multiplier']})")
                elif current_edits >= 2:
                    st.warning("🔒 You have reached the limit of 2 modifications.")
                    st.info(f"Your Locked Bet: {user_bet_row.iloc[0]['Predicted Team']} (x{user_bet_row.iloc[0]['Multiplier']})")
                else:
                    # Place Bet UI
                    with st.expander("📝 Place / Modify Bet", expanded=False):
                        with st.form(f"form_{m_id}"):
                            c1, c2 = st.columns(2)
                            with c1:
                                p_team = st.radio("Winner", [match['Team 1'], match['Team 2']], key=f"team_{m_id}")
                                p_mult = st.select_slider("Multiplier", options=[1, 2, 3], key=f"mult_{m_id}")
                            with c2:
                                p_names = sorted(players_df['Name'].tolist()) if not players_df.empty else ["N/A"]
                                p_motm = st.selectbox("MOTM", p_names, key=f"motm_{m_id}")
                            
                            if st.form_submit_button("Confirm Prediction"):
                                # Atomic Update Logic
                                live_bets = get_bets_live()
                                mask = (live_bets['Player'].astype(str) == current_user) & (live_bets['MatchID'].astype(str) == m_id)
                                
                                if not live_bets[mask].empty:
                                    # Update your placeholder/existing row
                                    row_idx = live_bets[mask].index[0]
                                    live_bets.at[row_idx, 'Predicted Team'] = p_team
                                    live_bets.at[row_idx, 'Multiplier'] = p_mult
                                    live_bets.at[row_idx, 'Predicted MOTM'] = p_motm
                                    live_bets.at[row_idx, 'EditCount'] = current_edits + 1
                                    live_bets.at[row_idx, 'Timestamp'] = now_ist.strftime("%Y-%m-%d %H:%M:%S")
                                else:
                                    # Create new row if no placeholder exists
                                    new_row = pd.DataFrame([{
                                        "Player": current_user, "MatchID": m_id, "Predicted Team": p_team,
                                        "Multiplier": p_mult, "Predicted MOTM": p_motm, "EditCount": 1,
                                        "Timestamp": now_ist.strftime("%Y-%m-%d %H:%M:%S")
                                    }])
                                    live_bets = pd.concat([live_bets, new_row], ignore_index=True)
                                
                                conn.update(worksheet="Bets", data=live_bets)
                                st.success("Bet Saved!")
                                st.cache_data.clear()
                                time.sleep(1)
                                st.rerun()

st.divider()
st.subheader("📋 Upcoming Schedule")
st.dataframe(matches_df[matches_df['Winner'] == ""].head(10), hide_index=True, use_container_width=True)
