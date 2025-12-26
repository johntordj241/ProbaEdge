from __future__ import annotations

from typing import Any

import streamlit as st

from .auth import authenticate_user, create_user
from .subscription import plan_label, normalize_plan, UPGRADE_URL

LANDING_PAGE_STYLES = """
<style>
:root {
    --landing-dark: #05060d;
    --landing-card: rgba(12, 15, 27, 0.92);
    --landing-accent: #f54b64;
    --landing-accent-2: #f78361;
}
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 15% 20%, rgba(245, 75, 100, 0.18), transparent 45%),
                radial-gradient(circle at 80% 0%, rgba(247, 131, 97, 0.16), transparent 35%),
                var(--landing-dark);
}
[data-testid="stHeader"], [data-testid="stSidebar"] {
    background: transparent;
}
.landing-hero {
    padding: 2.5rem;
    border-radius: 1.75rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: linear-gradient(135deg, rgba(11, 14, 23, 0.95), rgba(10, 12, 26, 0.78));
    box-shadow: 0 30px 60px rgba(0, 0, 0, 0.65);
}
.landing-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    font-size: 0.75rem;
    letter-spacing: 0.1rem;
    text-transform: uppercase;
    background: rgba(245, 75, 100, 0.15);
    color: rgba(255, 255, 255, 0.75);
}
.landing-lede {
    font-size: 1.1rem;
    line-height: 1.6;
    color: rgba(255, 255, 255, 0.86);
    margin-top: 1rem;
}
.landing-feature-list {
    list-style: none;
    padding-left: 0;
    margin: 1.5rem 0 0;
}
.landing-feature-list li {
    position: relative;
    padding-left: 1.4rem;
    margin-bottom: 0.55rem;
    color: rgba(255, 255, 255, 0.8);
}
.landing-feature-list li::before {
    content: ">";
    position: absolute;
    left: 0;
    top: 0;
    color: var(--landing-accent-2);
    font-weight: 600;
}
.landing-card {
    padding: 2rem 1.75rem 1.5rem;
    border-radius: 1.5rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: var(--landing-card);
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6);
}
.landing-card [data-baseweb="tab-list"] {
    gap: 0.5rem;
}
.landing-card [data-baseweb="tab"] {
    border-radius: 999px !important;
}
.landing-card button[kind="secondary"] {
    border-radius: 999px;
}
@media (max-width: 768px) {
    .landing-hero {
        padding: 1.5rem;
    }
    .landing-card {
        padding: 1.5rem 1.25rem;
    }
}
</style>
"""


def _login_form(show_heading: bool = True) -> bool:
    if show_heading:
        st.subheader("Acces existant")
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email", placeholder="vous@club.com")
        password = st.text_input(
            "Mot de passe", type="password", key="login_password", placeholder="********"
        )
        submitted = st.form_submit_button("Continuer vers l'espace prive", use_container_width=True)
    if submitted:
        user = authenticate_user(email, password)
        if user:
            st.session_state["auth_user"] = user
            st.success("Connexion journalisee.")
            st.experimental_rerun()
            return True
        st.error("Identifiants incorrects.")
    st.caption("Chaque session est placee sous controle interne.")
    return False


def _register_form(show_heading: bool = True) -> bool:
    if show_heading:
        st.subheader("Demande d'acces")
    with st.form("register_form"):
        name = st.text_input("Nom complet", key="register_name", placeholder="Analyste Ligue 1")
        email = st.text_input("Email", key="register_email", placeholder="vous@club.com")
        password = st.text_input(
            "Mot de passe", type="password", key="register_password", placeholder="Min. 8 caracteres"
        )
        confirm = st.text_input(
            "Confirmer le mot de passe",
            type="password",
            key="register_confirm",
            placeholder="Repetez le mot de passe",
        )
        submitted = st.form_submit_button("Demander un acces", use_container_width=True)
    if submitted:
        if password != confirm:
            st.error("Les mots de passe ne correspondent pas.")
            return False
        try:
            user = create_user(email, password, name)
        except ValueError as exc:
            st.error(str(exc))
            return False
        st.session_state["auth_user"] = user
        st.success("Acces ouvert.")
        st.experimental_rerun()
        return True
    st.caption("Validation possible seulement apres revue interne.")
    return False


def ensure_authenticated() -> bool:
    if st.session_state.get("auth_user"):
        return True

    st.title("Espace d'analyse Proba Edge")
    st.markdown(LANDING_PAGE_STYLES, unsafe_allow_html=True)

    hero_col, form_col = st.columns([1.35, 1], gap="large")

    with hero_col:
        st.markdown(
            """
            <div class="landing-hero">
                <span class="landing-badge">Plateforme interne supervisée</span>
                <h2>Comprendre les matches avant d'agir</h2>
                <p class="landing-lede">
                    Proba Edge rassemble les projections chiffrées, les historiques terrain et la supervision
                    IA pour aider un analyste a expliquer un signal, documenter une hypothese ou fermer un dossier
                    lorsqu'il manque de preuves.
                </p>
                <p class="landing-lede">
                    L'objectif : savoir dans quel contexte intervenir, avec quels garde-fous,
                    et quand s'abstenir pour préserver le capital de decision.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("#### Type d'analyse")
        st.markdown(
            """
            <ul class="landing-feature-list">
                <li>Analyse probabiliste et contextuelle des matches de football.</li>
                <li>Couverture pre-match et live avec mise a jour continue de l'incertitude.</li>
                <li>Qualification d'un signal, de son contexte et de la decision associee (agir, temporiser, bloquer).</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("#### Ce que vous pouvez faire ici")
        st.markdown(
            """
            <ul class="landing-feature-list">
                <li>Comparer les projections, cartons, edges et historiques d'un match.</li>
                <li>Tracer les arbitrages comptes-rendus dans les journaux supervision.</li>
                <li>Interpeller le Coach IA pour obtenir une explication factuelle et courte.</li>
                <li>Activer les verrous quand les hypotheses sont trop fragiles.</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("#### Questions analytiques autorisees")
        st.markdown(
            """
            <ul class="landing-feature-list">
                <li>« Quels paramètres expliquent l'ecart entre projection et score attendu ? »</li>
                <li>« Quels filtres bloquent ce match en pre-match et pourquoi ? »</li>
                <li>« Quelle part d'incertitude est liee aux blessures non resolues ? »</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("#### Ce que vous ne trouverez pas ici")
        st.markdown(
            """
            <ul class="landing-feature-list">
                <li>Aucune recommandation de mise ou d'action instantanee.</li>
                <li>Pas de signaux opportunistes ni de promesses de gain.</li>
                <li>Aucun contournement des limites ou des refus documentes.</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Acces restreint : chaque session manipule des donnees internes et des historiques sensibles. "
            "Chaque utilisateur est identifiable et ses requetes sont auditees."
        )

    with form_col:
        with st.container():
            st.markdown('<div class="landing-card">', unsafe_allow_html=True)
            st.markdown("#### Centre d'acces securise")
            tabs = st.tabs(["Acces existant", "Demande d'acces"])
            with tabs[0]:
                _login_form(show_heading=False)
            with tabs[1]:
                _register_form(show_heading=False)
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("Les demandes peuvent rester en file d'attente sans delai garanti.")

    st.info("Si la donnee est insuffisante, le protocole privilegie la mise en pause.")
    return False


def render_account_sidebar(container: Any) -> None:
    user = st.session_state.get("auth_user")
    if not user:
        return
    container.markdown("### Mon compte")
    container.markdown(f"**{user.get('name', 'Utilisateur')}**")
    container.caption(user.get("email", ""))
    plan_code = normalize_plan(user.get("plan"))
    container.caption(f"Offre actuelle : {plan_label(plan_code)}")
    container.write(f"[Gerer mon abonnement]({UPGRADE_URL})")
    if container.button("Se deconnecter", key="logout_button"):
        st.session_state.pop("auth_user", None)
        container.success("Deconnexion effectuee.")
        st.experimental_rerun()
