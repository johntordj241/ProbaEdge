import streamlit as st
import pandas as pd
from utils.predictions import show_predictions as _original_show_predictions
from utils.journalist_ai import JournalistAnalyzer


def show_predictions_with_journalist(
    default_league_id=None,
    default_season=None,
    default_team_id=None,
):
    """Wrapper autour de show_predictions avec l'agent journaliste"""

    # Afficher les predictions normales
    _original_show_predictions(default_league_id, default_season, default_team_id)

    # Ajouter la section journaliste
    st.markdown("---")
    st.subheader("📰 Analyse Journalistique & Contexte")

    # Charger les données
    try:
        df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")
        df["fixture_date"] = pd.to_datetime(
            df["fixture_date"], utc=True, errors="coerce"
        )

        journalist = JournalistAnalyzer(df)

        # Interface pour sélectionner un match
        col1, col2 = st.columns(2)

        with col1:
            home_team = st.selectbox(
                "Équipe domicile",
                options=sorted(df["home_team"].unique()),
                key="journalist_home",
            )

        with col2:
            away_team = st.selectbox(
                "Équipe extérieur",
                options=sorted(df["away_team"].unique()),
                key="journalist_away",
            )

        # Chercher le match
        if st.button("🔍 Analyser ce match"):
            match_data = df[
                (df["home_team"] == home_team) & (df["away_team"] == away_team)
            ].sort_values("fixture_date", ascending=False)

            if len(match_data) > 0:
                latest = match_data.iloc[0]

                # Générer le rapport
                report = journalist.generate_journalism_report(
                    home_team=home_team,
                    away_team=away_team,
                    league=latest.get("league_id", "Unknown"),
                    prob_home=latest["prob_home"],
                    prob_draw=latest["prob_draw"],
                    prob_away=latest["prob_away"],
                    main_pick=latest["main_pick"],
                )

                # Afficher le rapport formaté
                st.markdown(journalist.format_for_display(report))

            else:
                st.warning(f"❌ Aucun match {home_team} vs {away_team} trouvé")

    except Exception as e:
        st.error(f"Erreur lors de l'analyse journalistique: {str(e)}")
