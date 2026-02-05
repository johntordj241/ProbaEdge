# utils/match_stats.py
import streamlit as st
from utils.api_calls import call_api

def get_match_statistics(fixture_id):
    return call_api("fixtures/statistics", {"fixture": fixture_id})

def get_match_events(fixture_id):
    return call_api("fixtures/events", {"fixture": fixture_id})

def get_match_lineups(fixture_id):
    return call_api("fixtures/lineups", {"fixture": fixture_id})

def show_match_statistics(stats):
    st.subheader("📊 Statistiques du match")
    for s in stats.get("response", []):
        team = s["team"]["name"]
        st.write(f"**{team}** : {s['statistics']}")
