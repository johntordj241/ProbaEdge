# football_app/utils/stats.py

import streamlit as st

def show_stats(team_id):
    st.subheader("📊 Statistiques de l'équipe")
    
    # Exemple simple à adapter
    stats = {
        "Possession": "55%",
        "Tirs cadrés": "6",
        "Passes réussies": "82%",
        "Fautes": "12"
    }

    for key, value in stats.items():
        st.write(f"{key} : {value}")


