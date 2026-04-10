import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time as dt_time
import pytz
import time

st.set_page_config(page_title="IPL Fantasy Hub", layout="wide")
ist = pytz.timezone('Asia/Kolkata')

# --- NEON STADIUM UI ---
st.markdown("""
    <style>
    /* Background & Global Fonts */
    .stApp {
        background: radial-gradient(circle at top right, #1e293b, #0f172a);
    }
    
    /* Top Profile Badge */
    .profile-badge {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 20px;
        margin-bottom: 25px;
        border-top: 4px solid #38bdf8;
    }

    /* Match Card - Glassmorphism */
    .match-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px;
        border-radius: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s ease;
    }
    .match-card:hover {
        transform: scale(1.01);
        border-color: #38bdf8;
    }
    
    .status-pill {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 50px;
        font-size: 0.7em;
        font-weight: bold;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    .status-open { background: #065f46; color: #34d399; box-shadow: 0 0 10px #065f46; }
    .status-closed { background: #7f1d1d; color: #f87171; }
    
    .vs-text {
        font-family: 'Courier New', monospace;
        color: #38bdf8;
        font-style: italic;
        margin: 0 10px;
    }

    /* Fun Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 100%);
        border: none;
        color: #0f172a;
        font-weight: 800;
        border-radius: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("⚡ IPL Fantasy Hub")

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
        m_df['MatchID'] = m_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
        
        def fix_date(date_str):
            try:
                parsed = pd.to_datetime(date_str)
                return parsed.replace(year=2026).date()
            except: return None
            
        m_df['Date_Parsed'] = m_df['Date'].apply(fix_date)
        return m_df, p_df
    except Exception as e:
        st.error(f"Load Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

def get_bets_live():
    try:
        b_df = conn.read(worksheet="Bets", ttl=0).dropna(how='all').fillna('')
        if not b_df.empty:
            b_df['MatchID'] = b_df['MatchID'].astype(str).str.split('.').str[0].str.strip()
            b_df['Player'] = b_df['Player'].astype(str).str.strip()
        return b_df
    except:
        return pd.DataFrame(columns=["Player", "MatchID", "Predicted Team", "Multiplier", "Predicted MOTM", "Timestamp"])

matches_df, players_df = get_static_data()
leaderboard_df = get_leaderboard()
bets_df = get_bets_live()

# --- 2. TOP BADGE (PROFILE) ---
st.markdown('<div class="profile-badge">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1.5, 1, 1])
with c1:
    current_user = st.selectbox("PLAYER PROFILE", ["S", "G", "T", "Shy", "Y", "D", "A"])
with c2:
    user_score = leaderboard_df[leaderboard_df['Player'] == current_user]['Total'].values
    score_val = user_score[0] if len(user_score) > 0 else 0
    st.metric("TOTAL POINTS", f"{score_val}")
with c3:
    rank = leaderboard_df['Total'].rank(ascending=False, method='min').iloc[0] if not leaderboard_df.empty else "-"
    st.metric("RANK", f"#{int(rank)}")
st.markdown('</div>', unsafe_allow_html=True)

# --- 3. MATCH CENTER ---
col_main, col_side = st.columns([2.3, 1])

with col_main:
    now_ist = datetime.now(ist)
    today_date = now_ist.date()
    todays_matches = matches_df[matches_df['Date_Parsed'] == today_date].sort_values('MatchID')
    
    if todays_matches.empty:
        st.info("No matches scheduled for today. Rest up!")
    else:
        for i, (idx, match) in enumerate(todays_matches.iterrows()):
            m_id = str(match['MatchID']).strip()
            match_time = dt_time(15, 30) if (len(todays_matches) > 1 and i == 0) else dt_time(19, 30)
            
            # Lockout Checks
            time_locked = now_ist.time() >= match_time
            match_completed = str(match['Winner']).strip() != ""
            is_locked = time_locked or match_completed
            
            user_bet = bets_df[(bets_df['Player'] == current_user) & (bets_df['MatchID'] == m_id)]
            has_bet = not user_bet.empty and str(user_bet.iloc[0]['Predicted Team']).strip() != ""
            
            status_class = "status-closed" if is_locked else "status-open"
            status_text = "Closed" if is_locked else "Live"

            st.markdown(f"""
                <div class="match-card">
                    <div class="status-pill {status_class}">{status_text}</div>
                    <div style="color: #94a3b8; font-size: 0.8em; letter-spacing: 1px;">MATCH {m_id} • {match['Venue']}</div>
                    <div style="font-size: 1.8em; font-weight: 800; margin: 10px 0; color: white;">
                        {match['Team 1']} <span class="vs-text">VS</span> {match['Team 2']}
                    </div>
                    <div style="color: #64748b; font-size: 0.9em;">
                        Lockout at {match_time.strftime('%I:%M %p')} IST
                    </div>
                </div>
            """, unsafe_allow_html=True)

            if is_locked:
                if match_completed:
                    st.error(f"🏁 Winner: {match['Winner']}")
                if has_bet:
                    st.info(f"🏆 Your Pick: {user_bet.iloc[0]['Predicted Team']} (x{user_bet.iloc[0]['Multiplier']})")
            else:
                with st.expander("PLACE YOUR PREDICTION", expanded=not has_bet):
                    with st.form(f"form_{m_id}"):
                        f1, f2 = st.columns(2)
                        with f1:
                            p_team = st.radio("Who wins?", [match['Team 1'], match['Team 2']], key=f"t_{m_id}")
                            p_mult = st.select_slider("Multiplier", options=[1, 2, 3], key=f"m_{m_id}")
                        with f2:
                            p_names = sorted(players_df['Name'].tolist()) if not players_df.empty else ["N/A"]
                            p_motm = st.selectbox("MOTM", p_names, key=f"p_{m_id}")
                        
                        if st.form_submit_button("LOCK IT IN"):
                            live_bets = get_bets_live()
                            mask = (live_bets['Player'] == current_user) & (live_bets['MatchID'] == m_id)
                            ts = now_ist.strftime("%Y-%m-%d %H:%M:%S")
                            
                            if not live_bets[mask].empty:
                                tidx = live_bets[mask].index[0]
                                live_bets.at[tidx, 'Predicted Team'] = p_team
                                live_bets.at[tidx, 'Multiplier'] = p_mult
                                live_bets.at[tidx, 'Predicted MOTM'] = p_motm
                                live_bets.at[tidx, 'Timestamp'] = ts
                            else:
                                new_row = pd.DataFrame([{"Player": current_user, "MatchID": m_id, "Predicted Team": p_team, "Multiplier": p_mult, "Predicted MOTM": p_motm, "Timestamp": ts}])
                                live_bets = pd.concat([live_bets, new_row], ignore_index=True)
                            
                            conn.update(worksheet="Bets", data=live_bets)
                            st.cache_data.clear()
                            st.balloons()
                            st.rerun()

with col_side:
    st.markdown("### 🏆 Hall of Fame")
    st.dataframe(leaderboard_df[['Player', 'Total']].sort_values(by='Total', ascending=False), hide_index=True, use_container_width=True)
    st.divider()
    with st.expander("📅 Full Schedule"):
        st.dataframe(matches_df[['MatchID', 'Date', 'Team 1', 'Team 2']].head(15), hide_index=True)
