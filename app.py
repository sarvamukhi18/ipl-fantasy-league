import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time as dt_time
import pytz
import time

st.set_page_config(page_title="IPL Betting Hub", layout="wide")
ist = pytz.timezone('Asia/Kolkata')

# --- UI STYLING ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #1E88E5; color: white; }
    .match-box { border: 1px solid #e0e0e0; padding: 20px; border-radius: 12px; background-color: #ffffff; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏏 IPL Betting Dashboard")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. DATA LOADING ---

@st.cache_data(ttl=86400)
def get_leaderboard():
    return conn.read(worksheet="Leaderboard", ttl="24h").fillna(0)

@st.cache_data(ttl=600)
def get_static_data():
    m_df = conn.read(worksheet="Matches", ttl="10m").fillna('')
    p_df = conn.read(worksheet="Players", ttl="1h").fillna('')
    # Ensure MatchID is a clean string
    m_df['MatchID'] = m_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
    return m_df, p_df

def get_bets_live():
    try:
        b_df = conn.read(worksheet="Bets", ttl=0).dropna(how='all').fillna('')
        if not b_df.empty:
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

# --- 2. THE USER INTERFACE ---
col_main, col_side = st.columns([2, 1])

with col_side:
    st.subheader("🏆 Standings")
    st.table(leaderboard_df)

with col_main:
    player_list = ["S", "G", "T", "Shy", "Y", "D", "A"]
    current_user = st.selectbox("Who are you?", player_list)
    
    # DATE FIX: Using YYYY-MM-DD to match your CSV file
    now_ist = datetime.now(ist)
    today_date = now_ist.strftime("%Y-%m-%d")
    
    # Find today's games
    todays_matches = matches_df[matches_df['Date'] == today_date].sort_values('MatchID')
    
    if todays_matches.empty:
        st.warning(f"No matches found for {today_date}. Please check the 'Matches' sheet dates.")
    else:
        for i, (idx, match) in enumerate(todays_matches.iterrows()):
            m_id = str(match['MatchID']).strip()
            
            # --- LOCKOUT LOGIC ---
            # 3:30 PM for first match of double-header, 7:30 PM for others
            match_time = dt_time(15, 30) if (len(todays_matches) > 1 and i == 0) else dt_time(19, 30)
            is_locked = now_ist.time() >= match_time
            
            # Check for existing row
            user_bet = bets_df[(bets_df['Player'] == current_user) & (bets_df['MatchID'] == m_id)]
            has_bet = not user_bet.empty and str(user_bet.iloc[0]['Predicted Team']).strip() != ""
            
            st.markdown(f"""
            <div class="match-box">
                <h3>Match {m_id}: {match['Team 1']} vs {match['Team 2']}</h3>
                <p>📍 Venue: {match['Venue']} | ⏰ Lockout: {match_time.strftime('%I:%M %p')}</p>
            </div>
            """, unsafe_allow_html=True)

            if is_locked:
                st.error("🔒 Betting is closed.")
            elif has_bet and user_bet.iloc[0]['EditCount'] >= 2:
                st.success(f"✅ Bet Finalized: {user_bet.iloc[0]['Predicted Team']} (x{user_bet.iloc[0]['Multiplier']})")
            else:
                with st.expander("👉 Place / Edit Bet"):
                    with st.form(f"form_{m_id}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            p_team = st.radio("Who will win?", [match['Team 1'], match['Team 2']], key=f"t_{m_id}")
                            p_mult = st.select_slider("Points Multiplier", options=[1, 2, 3], key=f"m_{m_id}")
                        with c2:
                            p_names = sorted(players_df['Name'].tolist()) if not players_df.empty else ["N/A"]
                            p_motm = st.selectbox("Man of the Match", p_names, key=f"p_{m_id}")
                        
                        if st.form_submit_button("Lock It In"):
                            # Refresh live data to prevent overwriting someone else
                            live_bets = get_bets_live()
                            
                            # CLEAN MATCHING
                            mask = (live_bets['Player'] == current_user) & (live_bets['MatchID'] == m_id)
                            
                            if not live_bets[mask].empty:
                                # UPDATE EXISTING ROW
                                target_idx = live_bets[mask].index[0]
                                live_bets.at[target_idx, 'Predicted Team'] = p_team
                                live_bets.at[target_idx, 'Multiplier'] = p_mult
                                live_bets.at[target_idx, 'Predicted MOTM'] = p_motm
                                live_bets.at[target_idx, 'EditCount'] = int(live_bets.at[target_idx, 'EditCount']) + 1
                                live_bets.at[target_idx, 'Timestamp'] = now_ist.strftime("%Y-%m-%d %H:%M")
                            else:
                                # ADD NEW ROW
                                new_row = pd.DataFrame([{
                                    "Player": current_user, "MatchID": m_id, "Predicted Team": p_team,
                                    "Multiplier": p_mult, "Predicted MOTM": p_motm, "EditCount": 1,
                                    "Timestamp": now_ist.strftime("%Y-%m-%d %H:%M")
                                }])
                                live_bets = pd.concat([live_bets, new_row], ignore_index=True)
                            
                            conn.update(worksheet="Bets", data=live_bets)
                            st.cache_data.clear()
                            st.balloons()
                            st.rerun()

st.divider()
st.subheader("📋 All Upcoming Matches")
st.dataframe(matches_df[matches_df['Winner'] == ""].head(15), hide_index=True, use_container_width=True)
