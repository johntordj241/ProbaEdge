from __future__ import annotations

from typing import Dict, List

import streamlit as st

from .ai_.module import is_openai_configured
from .ai_agent import ask_coach

SUGGESTIONS = [
    "Quel match a l'edge le plus élevé ce soir ?",
    "Combien miser avec ma bankroll sur le tip du jour ?",
    "Quelles alertes sont actives actuellement ?",
]


def _history() -> List[Dict[str, str]]:
    return st.session_state.setdefault("coach_chat_history", [])


def render_coach_widget() -> None:
    container = st.container()
    container.markdown(
        """
        <style>
        section.main div.block-container > div[data-testid="stVerticalBlock"]:last-child {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: min(380px, 90vw);
            z-index: 900;
            background: #11131f;
            border: 1px solid #2f3247;
            border-radius: 16px;
            padding: 1rem;
            box-shadow: 0 18px 40px rgba(0,0,0,0.55);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with container:
        st.markdown("#### 🤖 Coach IA (beta)")
        st.caption("Toujours basé sur tes edges ≥ 5% et ta bankroll.")

        if not is_openai_configured():
            st.info("Configure OPENAI_API_KEY pour activer le coach.")
            return

        cols = st.columns(len(SUGGESTIONS))
        for idx, label in enumerate(SUGGESTIONS):
            if cols[idx].button(label, key=f"coach_suggestion_{idx}"):
                st.session_state["coach_prefill"] = label

        default_value = st.session_state.pop("coach_prefill", "")
        with st.form("coach_widget_form", clear_on_submit=False):
            question = st.text_input("Pose ta question", value=default_value)
            submitted = st.form_submit_button("Demander Coach")

        history = _history()
        if submitted:
            cleaned = question.strip()
            if not cleaned:
                st.warning("Merci de saisir une question.")
            else:
                history.append({"role": "user", "content": cleaned})
                with st.spinner("Coach réfléchit..."):
                    try:
                        response = ask_coach(cleaned)
                    except Exception as exc:  # pragma: no cover
                        history.pop()
                        st.error(f"Coach indisponible : {exc}")
                    else:
                        history.append({"role": "assistant", "content": response.answer})

        if history:
            st.markdown("---")
            st.markdown("**Historique récent**")
            for message in history[-4:]:
                role = "👤" if message["role"] == "user" else "🤖"
                st.markdown(
                    f"<div style='background:#191b28;border-radius:8px;padding:0.5rem;margin-bottom:0.4rem;'>"
                    f"{role} {message['content']}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info(
                "Exemples : 'Quel match a l'edge le plus élevé ce soir ?', "
                "'Combien miser selon ma stratégie percent ?'."
            )
