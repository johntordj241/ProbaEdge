from __future__ import annotations

import streamlit as st


OFFERS = [
    {
        "name": "Starter Lite",
        "price": "Gratuit",
        "billing": "mode démo (données différées)",
        "tagline": "Découvrir ProbaEdge en lecture seule, sans IA ni quotas API.",
        "features": [
            "Dashboard + Matchs/Statistiques/Classement (données différées 1×/jour)",
            "Aucun enregistrement de bankroll ou historique",
            "Pas d'IA, pas d'alertes, pas de Social Engine",
            "Accès suspendu après 30 jours si pas de conversion",
        ],
        "cta_label": "Activer Starter Lite",
        "cta_link": "mailto:contact@probaedge.ai?subject=Starter%20Lite",
        "highlight": False,
    },
    {
        "name": "Starter",
        "price": "19 €",
        "billing": "mois, sans engagement",
        "tagline": "Dashboard complet + quotas limités (5 matchs/jour).",
        "features": [
            "Toutes les pages Streamlit (hors IA avancée)",
            "5 matchs suivis / jour",
            "Historique local & export CSV manuel",
            "Sans IA ni alertes temps réel",
        ],
        "cta_label": "Demander un accès Starter",
        "cta_link": "mailto:contact@probaedge.ai?subject=Accès%20Starter",
        "highlight": False,
    },
    {
        "name": "Proba Edge Pro",
        "price": "59 €",
        "billing": "mois, résiliable",
        "tagline": "Tout le moteur multi-couches + alertes & Social Engine.",
        "features": [
            "Prédictions, cartes IA, module Belles cotes",
            "IA OpenAI on-demand + scénarios Over/Under filtrés",
            "Suivi bankroll complet & scripts backfill/train/deploy",
            "Alertes Slack/Discord, Social Engine (Markdown + publication)",
            "Mode hors-ligne + supervision + rapports Supabase",
        ],
        "cta_label": "Souscrire à l’offre Pro",
        "cta_link": "mailto:contact@probaedge.ai?subject=Souscription%20Pro",
        "highlight": True,
    },
    {
        "name": "Elite",
        "price": "89 €",
        "billing": "mois, prioritaire",
        "tagline": "Scénarios IA avancés, diffusion multi-canal et support VIP.",
        "features": [
            "Tout Pro + scénarios IA what-if & moteur secondaire (roadmap)",
            "Profils bankroll multiples & quotas API doublés",
            "Diffusion automatisée email / Telegram / X",
            "Rapports Supabase étendus, feedback tracker & support prioritaire",
            "Intégration aux workflows d’équipe (webhooks personnalisés)",
        ],
        "cta_label": "Parler avec l’équipe",
        "cta_link": "mailto:contact@probaedge.ai?subject=Offre%20Elite",
        "highlight": False,
    },
]


FAQ_ENTRIES = [
    (
        "Comment se passe la facturation ?",
        "Facturation mensuelle en début de période via Stripe ou virement. Résiliation possible à tout moment, l'accès reste actif jusqu'à la fin du mois en cours.",
    ),
    (
        "Puis-je tester avant de m'abonner ?",
        "Starter Lite est une version gratuite en lecture seule (données différées). Pour Starter/Pro/Elite, nous proposons un essai de 7 jours remboursable si l'outil ne correspond pas à vos besoins (hors quotas API consommés).",
    ),
    (
        "Que se passe-t-il si les quotas API explosent ?",
        "Les offres Pro/Elite incluent les quotas API-Football, OpenWeather, OpenAI et Supabase nécessaires. Au-delà, nous adaptons dynamiquement les limites ou proposons un add-on dédié.",
    ),
    (
        "Quelles sont les limites d'usage quotidiennes ?",
        "Starter : 5 matchs/jour, pas d'IA. Pro : 60 matchs/jour, IA et alertes incluses. Elite : 120 matchs/jour, scénarios IA avancés et diffusion automatique.",
    ),
    (
        "Puis-je upgrader/downgrader quand je veux ?",
        "Oui. Les changements prennent effet immédiatement ; la différence est proratisée sur la prochaine facture.",
    ),
    (
        "Comment fonctionne le support ?",
        "Starter : email en 48h ouvrées. Pro : Slack privé + email en 24h. Elite : channel dédié + astreinte matchday.",
    ),
    (
        "Que couvre exactement l'offre Elite ?",
        "Tous les modules Pro, plus scénarios IA what-if, moteur secondaire, quotas doublés, multi-bankroll, diffusion Telegram/X/email et support prioritaire.",
    ),
    (
        "Proposez-vous des remboursements ?",
        "Les abonnements sont sans engagement : si vous résiliez avant la prochaine échéance, il n'y a pas de facturation supplémentaire. Un remboursement au prorata est possible en cas d'incident majeur imputable à la plateforme (>24h).",
    ),
    (
        "Les données sont-elles partagées avec des tiers ?",
        "Non. Les données de bankroll, feedback et historiques restent dans votre environnement. Seuls les appels API nécessaires à la collecte (Football, météo, IA) sortent de l'application.",
    ),
    (
        "Puis-je connecter mes propres secrets (API, webhooks) ?",
        "Oui. Chaque plan permet de charger vos clés via `.env` ou l'écran Profil > Secrets. Elite inclut un onboarding assisté et la rotation automatique des clés.",
    ),
]


def _render_plan_card(plan: dict[str, object]) -> None:
    border = "2px solid #f97316" if plan.get("highlight") else "1px solid #dddddd"
    with st.container():
        st.markdown(
            f"""
            <div style="border:{border}; border-radius:12px; padding:18px; min-height:320px;">
                <h3 style="margin-bottom:4px;">{plan['name']}</h3>
                <p style="margin:0; font-size:1.5rem; font-weight:bold;">{plan['price']}</p>
                <p style="margin-top:0; color:#666;">{plan['billing']}</p>
                <p>{plan['tagline']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for feature in plan["features"]:
            st.write(f"✅ {feature}")
        st.markdown(
            f"[{plan['cta_label']}]({plan['cta_link']})",
            help="Redirection email pour finaliser la souscription.",
        )


def show_offers() -> None:
    st.header("Offres & Abonnements")
    st.caption("Choisissez le niveau qui correspond à votre pratique.")

    cols = st.columns(len(OFFERS))
    for column, plan in zip(cols, OFFERS):
        with column:
            _render_plan_card(plan)

    st.markdown("---")
    st.subheader("FAQ express")
    for question, answer in FAQ_ENTRIES:
        with st.expander(question, expanded=False):
            st.write(answer)

    st.markdown("---")
    st.info(
        "Besoin d'un pack sur-mesure (accès data, branding club, API) ? "
        "[Écrivez-nous](mailto:contact@probaedge.ai) pour une proposition dédiée."
    )


__all__ = ["show_offers"]
