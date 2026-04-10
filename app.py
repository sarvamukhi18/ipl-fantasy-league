import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time as dt_time
import pytz
import time

st.set_page_config(page_title="IPL Fantasy League", layout="wide")
ist = pytz.timezone('Asia/Kolkata')

# --- SPORTY RED & BLACK UI ---
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    
    /* Header Section */
    .main-header {
        background: linear-gradient(90deg, #d32f2f 0%, #000000 100%);
        padding: 20px;
        margin-top: -75px; 
        border-bottom: 3px solid #ff5252;
        margin-bottom: 20px;
    }
    
    /* Match & Result Cards */
    .match-card, .result-card {
        background: #121212;
        border-left: 5px solid #d32f2f;
        padding: 18px;
        border-radius: 8px;
        margin-bottom: 15px;
        box-shadow: 4px 4px 10px rgba(0,0,0,0.5);
    }
    .result-card { border-left: 5px solid #444; }

    .status-pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7em;
        font-weight: 900;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .status-open { background: #d32f2f; color: white; }
    .status-closed { background: #333; color: #888; }
    
    .team-header { font-family: 'Arial Black', sans-serif; text-transform: uppercase; color: white; }
    
    /* Sporty Buttons */
    .stButton>button {
        background: #d32f2f;
        border: none;
        color: white;
        font-weight: 900;
        border-radius: 4px;
        text-transform: uppercase;
        width: 100%;
    }
    .stButton>button:hover { background: #ff5252; box-shadow: 0 0 10px #d32f2f; }
    
    /* Clean up form spacing */
    .stForm { border: none !important; padding: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. DATA LOADING ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=86400)
def get_leaderboard():
    return conn.read(worksheet="Leaderboard", ttl="24h").fillna(0)

@st.cache_data(ttl=600)
def get_static_data():
    try:
        m_df = conn.read(worksheet="Matches", ttl="10m").fillna('')
        p_df = conn.read(worksheet="Players", ttl="1h").fillna('')
        m_df['MatchID'] = m_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
        def fix_date(date_str):
            try:
                parsed = pd.to_datetime(date_str)
                return parsed.replace(year=2026).date()
            except: return None
        m_df['Date_Parsed'] = m_df['Date'].apply(fix_date)
        return m_df, p_df
    except: return pd.DataFrame(), pd.DataFrame()

def get_bets_live():
    try:
        b_df = conn.read(worksheet="Bets", ttl=0).dropna(how='all').fillna('')
        if not b_df.empty:
            b_df['MatchID'] = b_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
            b_df['Player'] = b_df['Player'].astype(str).str.strip()
        return b_df
    except: return pd.DataFrame(columns=["Player", "MatchID", "Predicted Team", "Multiplier", "Predicted MOTM", "Timestamp"])

matches_df, players_df = get_static_data()
leaderboard_df = get_leaderboard()
bets_df = get_bets_live()

# --- 2. HEADER & PROFILE ---
st.markdown('<div class="main-header"><h1 style="color: white; margin: 0; font-family: Arial Black;">🏏 IPL FANTASY LEAGUE</h1></div>', unsafe_allow_html=True)

with st.container():
    c1, c2 = st.columns([2, 1])
    with c1:
        current_user = st.selectbox("PLAYER", ["S", "G", "T", "Shy", "Y", "D", "A"])
    with c2:
        user_score = leaderboard_df[leaderboard_df['Player'] == current_user]['Total'].values
        score_val = user_score[0] if len(user_score) > 0 else 0
        st.metric("POINTS", f"{score_val}")

st.divider()

# --- 3. MAIN CONTENT ---
col_main, col_side = st.columns([2.3, 1])

with col_main:
    now_ist = datetime.now(ist)
    today_date = now_ist.date()
    
    tab1, tab2 = st.tabs(["⚡ LIVE MATCHES", "🏁 RECENT RESULTS"])
    
    with tab1:
        todays_matches = matches_df[matches_df['Date_Parsed'] == today_date].sort_values('MatchID')
        if todays_matches.empty:
            st.info("No matches today. Check the schedule.")
        else:
            for i, (idx, match) in enumerate(todays_matches.iterrows()):
                m_id = str(match['MatchID']).strip()
                match_time = dt_time(15, 30) if (len(todays_matches) > 1 and i == 0) else dt_time(19, 30)
                is_locked = (now_ist.time() >= match_time) or (str(match['Winner']).strip() != "")
                
                user_bet = bets_df[(bets_df['Player'] == current_user) & (bets_df['MatchID'] == m_id)]
                has_bet = not user_bet.empty and str(user_bet.iloc[0]['Predicted Team']).strip() != ""
                
                status_class = "status-closed" if is_locked else "status-open"
                status_text = "LOCKED" if is_locked else "LIVE"

                st.markdown(f"""
                    <div class="match-card">
                        <div class="status-pill {status_class}">{status_text}</div>
                        <div class="team-header" style="font-size: 1.4em;">{match['Team 1']} vs {match['Team 2']}</div>
                        <div style="color: #888; font-size: 0.8em;">Match {m_id} • Lockout: {match_time.strftime('%I:%M %p')}</div>
                    </div>
                """, unsafe_allow_html=True)

                if is_locked:
                    if has_bet: 
                        st.info(f"**Locked Bet:** {user_bet.iloc[0]['Predicted Team']} (x{user_bet.iloc[0]['Multiplier']})")
                    else:
                        st.warning("No bet was placed before lockout.")
                else:
                    # REMOVED EXPANDER - Form is now Always Visible
                    with st.form(f"form_{m_id}"):
                        f1, f2 = st.columns(2)
                        with f1:
                            p_team = st.radio("Winner", [match['Team 1'], match['Team 2']], key=f"t_{m_id}")
                            p_mult = st.select_slider("Multiplier", options=[1, 2, 3], key=f"m_{m_id}")
                        with f2:
                            p_names = sorted(players_df['Name'].tolist()) if not players_df.empty else ["N/A"]
                            p_motm = st.selectbox("MOTM", p_names, key=f"p_{m_id}")
                        
                        if st.form_submit_button("SUBMIT"):
                            ts = now_ist.strftime("%Y-%m-%d %H:%M:%S")
                            live_bets = get_bets_live()
                            mask = (live_bets['Player'] == current_user) & (live_bets['MatchID'] == m_id)
                            
                            if not live_bets[mask].empty:
                                tidx = live_bets[mask].index[0]
                                live_bets.loc[tidx, ['Predicted Team', 'Multiplier', 'Predicted MOTM', 'Timestamp']] = [p_team, p_mult, p_motm, ts]
                            else:
                                new_row = pd.DataFrame([{"Player": current_user, "MatchID": m_id, "Predicted Team": p_team, "Multiplier": p_mult, "Predicted MOTM": p_motm, "Timestamp": ts}])
                                live_bets = pd.concat([live_bets, new_row], ignore_index=True)
                            
                            conn.update(worksheet="Bets", data=live_bets)
                            st.cache_data.clear()
                            st.success("Saved!")
                            st.rerun()

    with tab2:
        completed = matches_df[matches_df['Winner'] != ''].sort_values('MatchID', ascending=False).head(5)
        if completed.empty:
            st.write("No results recorded yet.")
        else:
            for _, row in completed.iterrows():
                st.markdown(f"""
                    <div class="result-card">
                        <div style="color: #d32f2f; font-weight: bold; font-size: 0.8em;">MATCH {row['MatchID']} RESULT</div>
                        <div class="team-header" style="font-size: 1.2em;">{row['Team 1']} vs {row['Team 2']}</div>
                        <div style="margin-top: 5px; color: white;">Winner: <b style="color: #34d399;">{row['Winner']}</b></div>
                        <div style="color: white;">MOTM: <b>{row['MOTM']}</b></div>
                    </div>
                """, unsafe_allow_html=True)

with col_side:
    st.markdown("<h3 style='color: white;'>🏆 STANDINGS</h3>", unsafe_allow_html=True)
    st.dataframe(leaderboard_df[['Player', 'Total']].sort_values(by='Total', ascending=False), hide_index=True, use_container_width=True)
