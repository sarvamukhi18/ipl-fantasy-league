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
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #FF9800; color: white; }
    .match-box { border: 2px solid #1E88E5; padding: 20px; border-radius: 12px; background-color: #f8f9fa; margin-bottom: 15px; }
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
    try:
        m_df = conn.read(worksheet="Matches", ttl="10m").fillna('')
        p_df = conn.read(worksheet="Players", ttl="1h").fillna('')
        
        # Standardize MatchID
        m_df['MatchID'] = m_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
        
        # DATE STANDARDIZATION: Convert any date format in sheet to YYYY-MM-DD string
        m_df['Date'] = pd.to_datetime(m_df['Date']).dt.strftime('%Y-%m-%d')
        
        return m_df, p_df
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

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

# --- 2. USER INTERFACE ---
col_main, col_side = st.columns([2, 1])

with col_side:
    st.subheader("🏆 Leaderboard")
    st.table(leaderboard_df)

with col_main:
    player_list = ["S", "G", "T", "Shy", "Y", "D", "A"]
    current_user = st.selectbox("Select Your Name", player_list)
    
    # Get current IST date in YYYY-MM-DD
    now_ist = datetime.now(ist)
    today_date_str = now_ist.strftime("%Y-%m-%d")
    
    # Debug expander (Delete this once you see matches appearing)
    with st.expander("🛠 Debugging Information"):
        st.write(f"System Date (IST): {today_date_str}")
        if not matches_df.empty:
            st.write("Next 3 Match Dates in Sheet:", matches_df['Date'].head(3).tolist())

    # Find today's games
    todays_matches = matches_df[matches_df['Date'] == today_date_str].sort_values('MatchID')
    
    if todays_matches.empty:
        st.warning(f"No matches found for {today_date_str} in the sheet. Ensure your 'Date' column is formatted correctly.")
    else:
        for i, (idx, match) in enumerate(todays_matches.iterrows()):
            m_id = str(match['MatchID']).strip()
            
            # --- LOCKOUT LOGIC ---
            match_time = dt_time(15, 30) if (len(todays_matches) > 1 and i == 0) else dt_time(19, 30)
            is_locked = now_ist.time() >= match_time
            
            # Check for existing bet
            user_bet = bets_df[(bets_df['Player'] == current_user) & (bets_df['MatchID'] == m_id)]
            has_bet = not user_bet.empty and str(user_bet.iloc[0]['Predicted Team']).strip() != ""
            
            st.markdown(f"""
            <div class="match-box">
                <h2 style='margin:0;'>Match {m_id}</h2>
                <h3 style='color:#1E88E5;'>{match['Team 1']} vs {match['Team 2']}</h3>
                <p>🕒 Lockout: <b>{match_time.strftime('%I:%M %p')}</b></p>
            </div>
            """, unsafe_allow_html=True)

            if is_locked:
                st.error("🚫 Betting closed for this match.")
            elif has_bet and user_bet.iloc[0]['EditCount'] >= 2:
                st.success(f"✅ Final Bet: {user_bet.iloc[0]['Predicted Team']} (x{user_bet.iloc[0]['Multiplier']})")
            else:
                label = "Modify Bet" if has_bet else "Place Bet"
                with st.expander(f"👉 Click to {label}"):
                    with st.form(f"form_{m_id}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            p_team = st.radio("Who wins?", [match['Team 1'], match['Team 2']], key=f"t_{m_id}")
                            p_mult = st.select_slider("Multiplier", options=[1, 2, 3], key=f"m_{m_id}")
                        with c2:
                            p_names = sorted(players_df['Name'].tolist()) if not players_df.empty else ["N/A"]
                            p_motm = st.selectbox("MOTM", p_names, key=f"p_{m_id}")
                        
                        if st.form_submit_button("Lock In Prediction"):
                            live_bets = get_bets_live()
                            mask = (live_bets['Player'] == current_user) & (live_bets['MatchID'] == m_id)
                            
                            if not live_bets[mask].empty:
                                target_idx = live_bets[mask].index[0]
                                live_bets.at[target_idx, 'Predicted Team'] = p_team
                                live_bets.at[target_idx, 'Multiplier'] = p_mult
                                live_bets.at[target_idx, 'Predicted MOTM'] = p_motm
                                live_bets.at[target_idx, 'EditCount'] = int(live_bets.at[target_idx, 'EditCount']) + 1
                                live_bets.at[target_idx, 'Timestamp'] = now_ist.strftime("%Y-%m-%d %H:%M")
                            else:
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
st.subheader("📅 Season Schedule")
st.dataframe(matches_df[matches_df['Winner'] == ""].head(10), hide_index=True, use_container_width=True)
