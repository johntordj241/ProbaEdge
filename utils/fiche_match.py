import streamlit as st

def format_fixtures(fixtures):
    if not fixtures:
        st.warning("Aucun match trouvé pour cette équipe.")
        return
    
    for match in fixtures:
        try:
            home_team = match["teams"]["home"]["name"]
            away_team = match["teams"]["away"]["name"]
            date = match["fixture"]["date"]

            st.markdown(f"### 🏟️ {home_team} vs {away_team}")
            st.caption(f"📅 {date}")
            st.write("---")
        except Exception as e:
            st.error(f"Erreur de formatage d'un match : {e}")
