"""
Betting Discipline Checklist - Ensure proper risk management before placing bets
"""

import streamlit as st
import pandas as pd
from datetime import datetime


def show_betting_checklist():
    """
    Display a mandatory checklist before betting
    Prevents emotional and over-aggressive betting
    """
    st.markdown("## 🛡️ CHECKLIST AVANT DE PARIER")
    st.markdown(
        """
    ⚠️ **OBLIGATOIRE** - Complete this checklist BEFORE placing any bet on Betclic
    """
    )

    # Create a form for the checklist
    with st.form(key="betting_checklist_form"):
        st.markdown("### Vérifications Essentielles:")

        col1, col2 = st.columns([0.05, 0.95])

        with col1:
            st.write("")

        with col2:
            # Checkbox 1: Algorithm recommendation
            check1 = st.checkbox(
                "✅ J'ai lu la RECOMMANDATION de l'algorithme",
                value=False,
                key="check_algo_rec",
            )
            st.caption("L'algo te dit quel match et quelle confiance")

        st.divider()

        with col2:
            # Checkbox 2: Bet amount
            check2 = st.checkbox(
                "✅ Je mise le MONTANT EXACT proposé par l'app (pas plus)",
                value=False,
                key="check_amount",
            )
            st.caption("Max 2-3% de ta bankroll. Ne dépasse JAMAIS.")

        st.divider()

        with col2:
            # Checkbox 3: Odds
            check3 = st.checkbox(
                "✅ La cote est >= 1.90 (ou recommandée)", value=False, key="check_odds"
            )
            st.caption("Cotes basses (1.60) = risqué pour peu de gain")

        st.divider()

        with col2:
            # Checkbox 4: Bet type
            check4 = st.checkbox(
                "✅ C'est un pari SIMPLE (pas combo)", value=False, key="check_simple"
            )
            st.caption("Combos = 60% × 60% = seulement 36% de chance")

        st.divider()

        with col2:
            # Checkbox 5: Confidence
            check5 = st.checkbox(
                "✅ Ma confiance personnelle est > 60%",
                value=False,
                key="check_confidence",
            )
            st.caption("Si tu hésite = NE PARIE PAS")

        st.divider()

        # Submit button
        submitted = st.form_submit_button(
            label="✅ VALIDER - Je suis prêt à parier",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            all_checked = check1 and check2 and check3 and check4 and check5

            if all_checked:
                st.success("✅ CHECKLIST COMPLÈTE!")
                st.balloons()

                # Save bet record
                save_bet_attempt(
                    status="approved", timestamp=datetime.now(), checks_passed=5
                )

                st.info(
                    """
                ✅ Tu peux maintenant placer ton pari sur Betclic.
                
                RAPPEL:
                1. Va sur Betclic
                2. Cherche le match recommandé
                3. Place le pari avec le montant EXACT
                4. Reviens noter le résultat dans l'app
                """
                )

            else:
                unchecked_count = 5 - sum([check1, check2, check3, check4, check5])
                st.error(
                    f"❌ CHECKLIST INCOMPLÈTE ({unchecked_count} case(s) non cochée(s))"
                )
                st.warning(
                    """
                🛑 **STOP!** Ne parie pas tant que tu n'as pas coché TOUS les cases.
                
                Si tu as du mal à cocher une case = c'est un SIGNAL ROUGE
                Ne force pas. Observe seulement aujourd'hui.
                """
                )

    st.divider()


def show_bankroll_calculator():
    """
    Show bankroll management calculator
    """
    st.markdown("## 💰 GESTION DE BANKROLL")

    bankroll = st.number_input(
        "Quel est ton bankroll total? (€)",
        min_value=100,
        max_value=100000,
        value=10000,
        step=100,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        max_per_bet_2pct = bankroll * 0.02
        st.metric("2% (Sûr)", f"{max_per_bet_2pct:.0f}€")

    with col2:
        max_per_bet_3pct = bankroll * 0.03
        st.metric("3% (Acceptable)", f"{max_per_bet_3pct:.0f}€")

    with col3:
        max_per_bet_5pct = bankroll * 0.05
        st.metric("5% (TROP RISQUÉ)", f"{max_per_bet_5pct:.0f}€", delta="⚠️")

    st.warning(
        f"""
    ⚠️ **RÈGLE D'OR:**
    - Ne mise JAMAIS plus de 3% par pari ({max_per_bet_3pct:.0f}€)
    - 2% c'est SAFE ({max_per_bet_2pct:.0f}€)
    - Si tu as perdu récemment = mise 1% seulement
    """
    )

    st.divider()


def show_bet_history_simple():
    """
    Simple bet tracking interface
    """
    st.markdown("## 📊 HISTORIQUE DE TES PARIS")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total paris placés", "0", "-")

    with col2:
        st.metric("Taux de réussite", "-", "-")

    st.info("Historique sera disponible une fois que tu auras commencé à parier")

    st.divider()


def save_bet_attempt(status: str, timestamp, checks_passed: int):
    """
    Save betting attempt to track discipline
    """
    try:
        import json
        from pathlib import Path

        bet_log = {
            "timestamp": timestamp.isoformat(),
            "status": status,
            "checks_passed": checks_passed,
        }

        log_file = Path.home() / ".probaedge_betting_log.json"

        # Append to log
        existing = []
        if log_file.exists():
            with open(log_file, "r") as f:
                existing = json.load(f)

        existing.append(bet_log)

        with open(log_file, "w") as f:
            json.dump(existing, f, indent=2)

    except Exception as e:
        pass  # Silent fail


# Main display function
def show_discipline_center():
    """
    Main function to show all discipline-related widgets
    """
    st.title("🛡️ CENTRE DE DISCIPLINE - ProbaEdge")
    st.markdown(
        """
    Cet espace t'aide à respecter LA DISCIPLINE.
    C'est ça qui a manqué. C'est ça qui va te faire gagner.
    """
    )

    tab1, tab2, tab3 = st.tabs(["🛡️ Checklist", "💰 Bankroll", "📊 Historique"])

    with tab1:
        show_betting_checklist()

    with tab2:
        show_bankroll_calculator()

    with tab3:
        show_bet_history_simple()


if __name__ == "__main__":
    show_discipline_center()
