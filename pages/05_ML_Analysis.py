"""Page Streamlit pour analyse complète du modèle ML"""

import streamlit as st
from utils.ml_dashboard import (
    show_ml_model_stats,
    show_betting_type_performance,
    show_league_performance,
    show_simple_vs_combo_stats,
)
from utils.ml_prediction_engine import (
    MODEL_STATS,
    BEST_BET_TYPES,
    BEST_LEAGUES,
    SIMPLE_VS_COMBO,
)


st.set_page_config(
    page_title="Analyse ML",
    layout="wide",
    page_icon="🤖",
)

st.title("🤖 Analyse du Modèle ML de Prédiction")

st.markdown(
    """
Ce modèle ML a été entraîné sur **411 paris réels** avec un historique complet de résultats.
Il utilise **6 features optimales** pour prédire la confiance de vos sélections.
"""
)

# Section des stats globales
st.markdown("---")
st.markdown("## 📈 Performance Globale du Modèle")

stats_cols = st.columns(4)

with stats_cols[0]:
    st.metric(
        "ROC-AUC Score",
        f"{MODEL_STATS['roc_auc']*100:.1f}%",
        help="Mesure la discrimination du modèle: 69.6% signifie +19.6% vs aléatoire (50%)",
    )

with stats_cols[1]:
    st.metric(
        "Accuracy",
        f"{MODEL_STATS['accuracy']*100:.1f}%",
        help="Pourcentage de prédictions correctes sur les 411 paris",
    )

with stats_cols[2]:
    st.metric(
        "Win Rate",
        f"{MODEL_STATS['win_rate']*100:.1f}%",
        help="Taux de victoire réel: 60.6% gain",
    )

with stats_cols[3]:
    st.metric(
        "Dataset",
        f"{MODEL_STATS['valid_predictions']} paris",
        help="Nombre total de paris utilisés pour l'entraînement",
    )

st.info(
    """
✅ **Interprétation:** 
- Un ROC-AUC de 69.6% signifie que le modèle classe correctement 69.6% des paires (réussi vs échoué)
- Le modèle surpasse largement l'aléatoire (50%) et même les modèles basiques (55-60%)
- 60.6% de win rate sur 411 paris = modèle fiable et profitable
"""
)

# Analyse des types de paris
st.markdown("---")
st.markdown("## 📊 Performance par Type de Pari")

st.markdown("### Quels types de paris réussissent le mieux?")

tab1, tab2 = st.tabs(["Vue Métrique", "Détails"])

with tab1:
    show_betting_type_performance()

with tab2:
    st.markdown("### Détail des types de paris")
    for bet_type, stats in sorted(
        BEST_BET_TYPES.items(), key=lambda x: x[1]["win_rate"], reverse=True
    ):
        win_pct = stats["win_rate"] * 100

        if win_pct >= 70:
            icon = "🟢 EXCELLENT"
        elif win_pct >= 60:
            icon = "🟡 BON"
        else:
            icon = "🔴 À AMÉLIORER"

        st.markdown(
            f"""
#### {icon} - {bet_type}
- **Taux de réussite:** {win_pct:.1f}%
- **Nombre de paris:** {stats['count']}
- **Résultats:** {int(stats['win_rate'] * stats['count'])}/{stats['count']} gagnés
        """
        )

# Analyse par championnat
st.markdown("---")
st.markdown("## 🏟️ Performance par Championnat")

st.markdown("### Quels championnats sont les plus fiables?")

tab1, tab2 = st.tabs(["Vue Métrique", "Détails"])

with tab1:
    show_league_performance()

with tab2:
    st.markdown("### Détail par championnat")
    sorted_leagues = sorted(
        BEST_LEAGUES.items(), key=lambda x: x[1]["win_rate"], reverse=True
    )

    for league_id, stats in sorted_leagues:
        win_pct = stats["win_rate"] * 100

        if win_pct >= 70:
            icon = "🟢 EXCELLENT"
        elif win_pct >= 60:
            icon = "🟡 BON"
        else:
            icon = "🔴 À AMÉLIORER"

        st.markdown(
            f"""
#### {icon} - {stats['name']}
- **Taux de réussite:** {win_pct:.1f}%
- **Nombre de matchs:** {stats['count']}
- **Résultats:** {int(stats['win_rate'] * stats['count'])}/{stats['count']} prédictions correctes
        """
        )

# Simple vs Combiné
st.markdown("---")
st.markdown("## 🎯 Paris Simple vs Combiné")

st.markdown("### Lequel est plus rentable?")

col1, col2 = st.columns(2)

with col1:
    simple_stats = SIMPLE_VS_COMBO["simple"]
    simple_pct = simple_stats["win_rate"] * 100

    st.metric(
        "Paris Simples",
        f"{simple_pct:.1f}%",
        f"{int(simple_stats['win_rate'] * simple_stats['count'])}/{simple_stats['count']} gagnés",
    )

    st.markdown(
        f"**Paris simples:** {simple_pct:.1f}% de succès sur {simple_stats['count']} paris"
    )

with col2:
    combo_stats = SIMPLE_VS_COMBO["combo"]
    combo_pct = combo_stats["win_rate"] * 100

    st.metric(
        "Paris Combinés",
        f"{combo_pct:.1f}%",
        f"{int(combo_stats['win_rate'] * combo_stats['count'])}/{combo_stats['count']} gagnés",
    )

    st.markdown(
        f"**Paris combinés:** {combo_pct:.1f}% de succès sur {combo_stats['count']} paris"
    )

# Recommandations
diff_pct = simple_pct - combo_pct
if diff_pct > 1:
    st.success(
        f"""
✅ **Recommandation:** Les paris simples surpassent les combinés de {abs(diff_pct):.1f}%
    
Cette différence suggère que les combinés ajoutent de la complexité sans bénéfice supplémentaire.
Privilégiez les paris simples pour une meilleure rentabilité.
    """
    )
elif abs(diff_pct) <= 1:
    st.info(
        f"""
✅ **Recommandation:** Pas de différence significative ({abs(diff_pct):.1f}%)
    
Simple et combiné sont équivalents. Choisissez selon votre préférence et votre gestion de bankroll.
    """
    )
else:
    st.warning(
        f"""
✅ **Recommandation:** Les combinés surpassent les simples de {abs(diff_pct):.1f}%
    
Les paris combinés pourraient être plus rentables dans ce contexte.
    """
    )

# Features importantes
st.markdown("---")
st.markdown("## ⚙️ Features du Modèle")

st.markdown(
    """
Le modèle utilise **6 features optimales** pour faire ses prédictions:

1. **feature_max_prob** (Importance: 54.1%) - La probabilité maximum d'une issue
2. **feature_total_pick_over** (31.1%) - Le total des sélections "over"
3. **feature_over_under_diff** (24.9%) - Différence over/under
4. **feature_home_draw_diff** (14.2%) - Différence domicile/nul
5. **feature_main_confidence_norm** - Confiance normalisée du pronostic
6. **feature_home_away_diff** - Différence domicile/extérieur

💡 **Note:** `feature_max_prob` seule explique 54% de la puissance prédictive du modèle!
"""
)

# Histogramme des scores
st.markdown("---")
st.markdown("## 📊 Distribution du Dataset")

st.markdown(
    f"""
- **Total de prédictions:** {MODEL_STATS['valid_predictions']}
- **Prédictions correctes:** {int(MODEL_STATS['valid_predictions'] * MODEL_STATS['win_rate'])}
- **Prédictions incorrectes:** {int(MODEL_STATS['valid_predictions'] * (1 - MODEL_STATS['win_rate']))}
- **Version du modèle:** v{MODEL_STATS['model_version']}
"""
)

# Footer
st.markdown("---")
st.markdown(
    """
<div style="text-align: center; color: #666; margin-top: 20px;">
    <p><strong>Modèle ML ProbaEdge</strong> | Entraîné sur 411 paris réels avec succès validé</p>
    <p>ROC-AUC: 69.6% | Accuracy: 61.2% | Win Rate: 60.6%</p>
</div>
""",
    unsafe_allow_html=True,
)
