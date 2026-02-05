"""
Widget affichant les stats et confiance du modèle ML
"""

import streamlit as st
from typing import Optional, Dict, Any


def show_ml_model_stats():
    """Affiche les stats du modèle ML entraîné"""
    from .ml_prediction_engine import MODEL_STATS

    st.markdown("### 🤖 Modèle ML de Prédiction")

    stats_cols = st.columns(4)

    with stats_cols[0]:
        st.metric(
            "ROC-AUC",
            f"{MODEL_STATS['roc_auc']*100:.1f}%",
            help="Performance du modèle vs aléatoire (50%)",
        )

    with stats_cols[1]:
        st.metric(
            "Accuracy",
            f"{MODEL_STATS['accuracy']*100:.1f}%",
            help="Taux de prédictions correctes",
        )

    with stats_cols[2]:
        st.metric(
            "Win Rate",
            f"{MODEL_STATS['win_rate']*100:.1f}%",
            help="Taux de victoire sur 411 paris",
        )

    with stats_cols[3]:
        st.metric(
            "Données",
            f"{MODEL_STATS['valid_predictions']}",
            help="Nombre de paris utilisés pour l'entraînement",
        )


def show_betting_type_performance():
    """Affiche la performance par type de pari"""
    from .ml_prediction_engine import BEST_BET_TYPES

    st.markdown("### 📊 Performance par Type de Pari")

    cols = st.columns(len(BEST_BET_TYPES))

    for idx, (bet_type, stats) in enumerate(BEST_BET_TYPES.items()):
        with cols[idx]:
            win_pct = stats["win_rate"] * 100

            # Couleur selon performance
            if win_pct >= 70:
                icon = "🟢"
            elif win_pct >= 60:
                icon = "🟡"
            else:
                icon = "🔴"

            st.metric(
                bet_type,
                f"{win_pct:.0f}%",
                f"n={stats['count']}",
                help=f"Taux de réussite sur {stats['count']} paris",
            )


def show_league_performance():
    """Affiche la performance par championnat"""
    from .ml_prediction_engine import BEST_LEAGUES

    st.markdown("### 🏟️ Performance par Championnat")

    cols = st.columns(2)

    # Trier par performance (descendante)
    sorted_leagues = sorted(
        BEST_LEAGUES.items(), key=lambda x: x[1]["win_rate"], reverse=True
    )

    for idx, (league_id, stats) in enumerate(sorted_leagues):
        with cols[idx % 2]:
            win_pct = stats["win_rate"] * 100

            if win_pct >= 70:
                icon = "🟢"
            elif win_pct >= 60:
                icon = "🟡"
            else:
                icon = "🔴"

            st.metric(
                f"{stats['name']}",
                f"{win_pct:.0f}%",
                f"n={stats['count']}",
                help=f"Taux de réussite sur {stats['count']} matchs",
            )


def show_simple_vs_combo_stats():
    """Affiche les stats simples vs combinés"""
    from .ml_prediction_engine import SIMPLE_VS_COMBO

    st.markdown("### 🎯 Simple vs Combiné")

    cols = st.columns(2)

    stats = SIMPLE_VS_COMBO

    with cols[0]:
        simple_pct = stats["simple"]["win_rate"] * 100
        st.metric(
            "Paris Simples",
            f"{simple_pct:.1f}%",
            f"n={stats['simple']['count']}",
            help=f"Taux de réussite sur {stats['simple']['count']} paris simples",
        )

    with cols[1]:
        combo_pct = stats["combo"]["win_rate"] * 100
        st.metric(
            "Paris Combinés",
            f"{combo_pct:.1f}%",
            f"n={stats['combo']['count']}",
            help=f"Taux de réussite sur {stats['combo']['count']} paris combinés",
        )

    # Insight
    diff = simple_pct - combo_pct
    if diff > 0:
        st.info(f"✅ Les paris simples surpassent les combinés de {abs(diff):.1f}%")
    else:
        st.info(f"✅ Les paris combinés surpassent les simples de {abs(diff):.1f}%")


def show_ml_analysis_dashboard():
    """Dashboard complet de l'analyse ML"""
    st.markdown("---")

    # Afficher les stats du modèle
    show_ml_model_stats()

    st.markdown("---")

    # Afficher les analyses de paris
    tab1, tab2, tab3 = st.tabs(["Types de Paris", "Championnats", "Simple vs Combiné"])

    with tab1:
        show_betting_type_performance()

    with tab2:
        show_league_performance()

    with tab3:
        show_simple_vs_combo_stats()
