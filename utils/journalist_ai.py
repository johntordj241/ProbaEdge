import pandas as pd
import json
from datetime import datetime
import os

# Charge depuis OpenAI ou locale
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except:
    OPENAI_AVAILABLE = False


class JournalistAnalyzer:
    """Agent IA journaliste-analyste pour contexte des matchs"""

    def __init__(self, df):
        self.df = df
        self.client = None
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            self.client = OpenAI()

    def get_h2h_history(self, home_team, away_team, limit=5):
        """Récupère les 5 derniers matchs H2H"""
        h2h = (
            self.df[
                (
                    (self.df["home_team"] == home_team)
                    & (self.df["away_team"] == away_team)
                )
                | (
                    (self.df["home_team"] == away_team)
                    & (self.df["away_team"] == home_team)
                )
            ]
            .sort_values("fixture_date", ascending=False)
            .head(limit)
        )

        history = []
        for idx, match in h2h.iterrows():
            is_home = match["home_team"] == home_team
            score = (
                f"{match['goals_home']}-{match['goals_away']}"
                if "goals_home" in match
                else "?"
            )
            result = match["result_winner"] if "result_winner" in match else "?"

            history.append(
                {
                    "date": match["fixture_date"].strftime("%d/%m/%Y"),
                    "opponent": match["away_team"] if is_home else match["home_team"],
                    "score": score,
                    "position": "Home" if is_home else "Away",
                    "result": result,
                }
            )

        return history

    def analyze_anomalies(self, home_team, away_team, prob_home, prob_away):
        """Détecte les anomalies et patterns suspects"""
        alerts = []

        # Anomalie 1: Probabilité déséquilibrée vs cote
        if prob_home > 0.85 and prob_away > 0.10:
            alerts.append(
                {
                    "type": "probabilité_incohérente",
                    "severity": "medium",
                    "message": f"⚠️ Probabilités incohérentes: Home {prob_home*100:.0f}% vs Away {prob_away*100:.0f}%",
                }
            )

        # Anomalie 2: Vérifier les séries récentes
        home_recent = (
            self.df[self.df["home_team"] == home_team]
            .sort_values("fixture_date", ascending=False)
            .head(5)
        )
        away_recent = (
            self.df[self.df["away_team"] == away_team]
            .sort_values("fixture_date", ascending=False)
            .head(5)
        )

        if len(home_recent) > 0 and len(away_recent) > 0:
            home_wins = len(
                home_recent[home_recent["result_winner"].isin(["home", "1"])]
            )
            away_wins = len(
                away_recent[away_recent["result_winner"].isin(["away", "2"])]
            )

            if home_wins == 0 and away_wins >= 3:
                alerts.append(
                    {
                        "type": "forme_contraste",
                        "severity": "high",
                        "message": f"🔴 {home_team} en mauvaise forme (0/5) vs {away_team} en bonne forme (3/5+)",
                    }
                )

        return alerts

    def generate_journalism_report(
        self, home_team, away_team, league, prob_home, prob_draw, prob_away, main_pick
    ):
        """Génère un rapport d'analyse journalistique"""

        report = {
            "timestamp": datetime.now().isoformat(),
            "match": f"{home_team} vs {away_team}",
            "league": league,
            "h2h": self.get_h2h_history(home_team, away_team),
            "anomalies": self.analyze_anomalies(
                home_team, away_team, prob_home, prob_away
            ),
            "warnings": [],
            "journalist_insight": None,
        }

        # Générer les warnings
        if len(report["h2h"]) > 0:
            recent_match = report["h2h"][0]
            if home_team in recent_match["opponent"]:
                # Le match H2H récent implique ces équipes
                report["warnings"].append(
                    f"ℹ️ Historique: {home_team} et {away_team} se sont affrontés le {recent_match['date']} ({recent_match['score']})"
                )

        # Insight IA si disponible
        if self.client:
            try:
                prompt = f"""Tu es un journaliste sportif analyste expert. Fournis une analyse courte (2-3 lignes) du match:
                
Match: {home_team} vs {away_team} ({league})
Probas: Home {prob_home*100:.0f}% | Draw {prob_draw*100:.0f}% | Away {prob_away*100:.0f}%
Main Pick: {main_pick}
Historique H2H: {json.dumps(report['h2h'][:3], ensure_ascii=False)}

Identifie les risques, pièges ou contextes importants que les pariants devraient connaître.
Réponds en français, de manière concise."""

                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=200,
                )

                report["journalist_insight"] = response.choices[0].message.content
            except Exception as e:
                report["journalist_insight"] = f"[Analyse IA indisponible: {str(e)}]"

        return report

    def format_for_display(self, report):
        """Formate le rapport pour affichage Streamlit"""
        formatted = f"## 📰 Analyse Journalistique\n\n"

        # H2H
        if report["h2h"]:
            formatted += "### 📊 Historique H2H\n"
            for h in report["h2h"][:3]:
                formatted += f"- {h['date']}: {h['position']} vs {h['opponent']} → {h['score']}\n"
            formatted += "\n"

        # Anomalies
        if report["anomalies"]:
            formatted += "### ⚠️ Anomalies Détectées\n"
            for alert in report["anomalies"]:
                emoji = "🔴" if alert["severity"] == "high" else "🟡"
                formatted += f"{emoji} {alert['message']}\n"
            formatted += "\n"

        # Insight IA
        if report["journalist_insight"]:
            formatted += "### 💭 Insight de l'Analyste\n"
            formatted += f"{report['journalist_insight']}\n"

        return formatted
