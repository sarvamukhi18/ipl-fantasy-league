import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time as dt_time
import pytz
import time

st.set_page_config(page_title="IPL Fantasy Hub", layout="wide")
ist = pytz.timezone('Asia/Kolkata')

# --- REFINED STADIUM DARK UI ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    
    /* Top Profile Section */
    .profile-container {
        background: #1e293b;
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #38bdf8;
        margin-bottom: 25px;
    }

    /* Match Card Styling */
    .match-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 15px;
        color: white;
    }
    
    .match-header {
        color: #94a3b8;
        font-size: 0.75em;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    
    .vs-text { color: #38bdf8; font-weight: bold; }
    
    /* Buttons & Forms */
    .stButton>button {
        border-radius: 8px;
        background-color: #38bdf8;
        color: #0f172a;
        font-weight: bold;
    }
    
    /* Hide Sidebar on Mobile if needed, but here we move elements to top */
    @media (max-width: 768px) {
        .stColumn { width: 100% !important; }
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏏 IPL Fantasy Hub")

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
            b_df['EditCount'] = pd.to_numeric(b_df['EditCount'], errors='coerce').fillna(0).astype(int)
        return b_df
    except:
        return pd.DataFrame(columns=["Player", "MatchID", "Predicted Team", "Multiplier", "Predicted MOTM", "EditCount", "Timestamp"])

matches_df, players_df = get_static_data()
leaderboard_df = get_leaderboard()
bets_df = get_bets_live()

# --- 2. MOBILE-FIRST TOP SECTION (PROFILE) ---
# We use a container to keep the profile always at the top
with st.container():
    st.markdown('<div class="profile-container">', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        current_user = st.selectbox("👤 Active Player", ["S", "G", "T", "Shy", "Y", "D", "A"])
    with c2:
        # Quick score display for the selected user
        user_score = leaderboard_df[leaderboard_df['Player'] == current_user]['Total'].values
        score_val = user_score[0] if len(user_score) > 0 else 0
        st.metric("Your Points", f"{score_val} pts")
    st.markdown('</div>', unsafe_allow_html=True)

# --- 3. MAIN DASHBOARD ---
col_main, col_side = st.columns([2, 1])

with col_main:
    now_ist = datetime.now(ist)
    today_date = now_ist.date()
    todays_matches = matches_df[matches_df['Date_Parsed'] == today_date].sort_values('MatchID')
    
    if todays_matches.empty:
        st.info(f"📅 No matches scheduled for today.")
    else:
        for i, (idx, match) in enumerate(todays_matches.iterrows()):
            m_id = str(match['MatchID']).strip()
            match_time = dt_time(15, 30) if (len(todays_matches) > 1 and i == 0) else dt_time(19, 30)
            is_locked = now_ist.time() >= match_time
            
            user_bet = bets_df[(bets_df['Player'] == current_user) & (bets_df['MatchID'] == m_id)]
            has_bet = not user_bet.empty and str(user_bet.iloc[0]['Predicted Team']).strip() != ""
            
            # Match Card UI
            st.markdown(f"""
                <div class="match-card">
                    <div class="match-header">Match {m_id} • {match['Venue']}</div>
                    <div style="font-size: 1.5em; font-weight: 700; margin: 8px 0;">
                        {match['Team 1']} <span class="vs-text">vs</span> {match['Team 2']}
                    </div>
                    <div style="color: #94a3b8; font-size: 0.85em;">
                        🕒 Lockout: {match_time.strftime('%I:%M %p')} IST
                    </div>
                </div>
            """, unsafe_allow_html=True)

            if is_locked:
                st.warning("🚫 Betting closed.")
                if has_bet: st.info(f"**Locked Bet:** {user_bet.iloc[0]['Predicted Team']} (x{user_bet.iloc[0]['Multiplier']})")
            elif has_bet and user_bet.iloc[0]['EditCount'] >= 2:
                st.success(f"✅ Pick Finalized: {user_bet.iloc[0]['Predicted Team']} (x{user_bet.iloc[0]['Multiplier']})")
            else:
                with st.expander("📝 Edit Prediction" if has_bet else "➕ Place Prediction", expanded=not has_bet):
                    with st.form(f"form_{m_id}"):
                        f1, f2 = st.columns(2)
                        with f1:
                            p_team = st.radio("Winner", [match['Team 1'], match['Team 2']], key=f"t_{m_id}")
                            p_mult = st.select_slider("Multiplier", options=[1, 2, 3], key=f"m_{m_id}")
                        with f2:
                            p_names = sorted(players_df['Name'].tolist()) if not players_df.empty else ["N/A"]
                            p_motm = st.selectbox("MOTM", p_names, key=f"p_{m_id}")
                        
                        if st.form_submit_button("Confirm Prediction"):
                            live_bets = get_bets_live()
                            mask = (live_bets['Player'] == current_user) & (live_bets['MatchID'] == m_id)
                            if not live_bets[mask].empty:
                                tidx = live_bets[mask].index[0]
                                live_bets.at[tidx, 'Predicted Team'] = p_team
                                live_bets.at[tidx, 'Multiplier'] = p_mult
                                live_bets.at[tidx, 'Predicted MOTM'] = p_motm
                                live_bets.at[tidx, 'EditCount'] = int(live_bets.at[tidx, 'EditCount']) + 1
                                live_bets.at[tidx, 'Timestamp'] = now_ist.strftime("%H:%M")
                            else:
                                new_row = pd.DataFrame([{"Player": current_user, "MatchID": m_id, "Predicted Team": p_team, "Multiplier": p_mult, "Predicted MOTM": p_motm, "EditCount": 1, "Timestamp": now_ist.strftime("%H:%M")}])
                                live_bets = pd.concat([live_bets, new_row], ignore_index=True)
                            conn.update(worksheet="Bets", data=live_bets)
                            st.cache_data.clear()
                            st.balloons()
                            st.rerun()

with col_side:
    st.markdown("### 🏆 Standings")
    st.dataframe(leaderboard_df[['Player', 'Total']].sort_values(by='Total', ascending=False), hide_index=True, use_container_width=True)
    st.divider()
    with st.expander("📅 Season Schedule"):
        st.dataframe(matches_df[['MatchID', 'Date', 'Team 1', 'Team 2']].head(15), hide_index=True)
