from __future__ import annotations

import streamlit as st

GUIDES = {
    "Bookmakers": [
        "Selectionner vos operateurs (profil) pour ne voir que les matchs pertinents.",
        "Surveiller la colonne 'Prediction' pour identifier les edges > 5%.",
        "Inclure matches sans cotes pour verifier les trous de couverture.",
        "Alerte : si le mode hors ligne est actif, les cotes peuvent etre depassees.",
        "Prompt IA : \"Quels matchs offrent un edge >5% sur les 3 prochains jours ?\"",
    ],
    "Buteurs": [
        "Surveiller la forme sur les 5 derniers matchs des buteurs majeurs.",
        "Comparer buts/minutes avec les attentes du modele IA.",
        "Identifier suspensions ou blessures affectant les leaders.",
        "Alerte : confirmer la presence dans le groupe avant de miser sur un buteur.",
        "Prompt IA : \"Quel buteur presente le meilleur ratio buts/minute pour la prochaine journee ?\"",
    ],
    "Cartons": [
        "Lister les joueurs sous menace de suspension (4e avertissement).",
        "Comparer les clubs les plus sanctionnes sur les 5 derniers matchs.",
        "Reperer les retours de suspension avant la prochaine journee.",
        "Alerte : verifier le corps arbitral pour anticiper un volume eleve de cartons.",
        "Prompt IA : \"Quels matchs risquent de generer le plus de cartons selon les historiques ?\"",
    ],
    "Classement": [
        "Verifier top 5 et zone rouge pour prioriser les analyses.",
        "Analyser la serie des 5 derniers matchs pour les clubs suivis.",
        "Comparer la difference de buts avec les concurrents directs.",
        "Prompt IA : \"Quelles equipes en progression risquent de basculer dans le top 5 cette semaine ?\"",
    ],
    "Cotes": [
        "Comparer les meilleures cotes 1X2 avec les probabilites IA (>5% edge).",
        "Verifier l'horodatage de mise a jour pour detecter les mouvements.",
        "Exporter le detail par bookmaker pour surveiller les variations.",
        "Prompt IA : \"Quels operateurs changent le plus rapidement leurs cotes aujourd'hui ?\"",
    ],
    "Dashboard": [
        "Verifier que la ligue par defaut est la bonne (profil > parametres).",
        "Observer le match mis en avant et rafraichir en cas de live (bouton).",
        "Consulter le classement top 10 pour identifier la dynamique actuelle.",
        "Prompt IA : \"Quels indicateurs du dashboard meritent une alerte aujourd'hui ?\"",
    ],
    "Guides": [
        "Passer chaque onglet et recenser les questions manquantes pour l'IA.",
        "Verifier que les exemples couvrent pre-match, live et usage data.",
        "Planifier l'ajout des nouveaux modules et avertissements manquants.",
        "Prompt IA : \"Quelles pages ont besoin de nouveaux prompts ou alertes cette semaine ?\"",
    ],
    "Supervision": [
        "Surveiller les indicateurs sidebar : quota restant, mode hors ligne actif.",
        "Relire docs/supervision.md avant toute purge ou bascule hors ligne.",
        "Toujours recharger les pages critiques en ligne avant de repasser offline.",
        "Alerte : basculer hors ligne bloque les ecritures historique/predictions.",
        "Prompt IA : \"Quels incidents supervision dois-je corriger en priorite ?\"",
    ],
    "H2H": [
        "Comparer les 5 derniers face-a-face pour reperer les tendances.",
        "Noter l'ecart moyen de buts et les scores recurrents.",
        "Verifier le statut domicile/exterieur pour calibrer la prediction.",
        "Prompt IA : \"Quels patterns H2H ressortent pour ce duel ?\"",
    ],
    "Historique": [
        "Mettre a jour au moins une fois par semaine pour conserver les 3 dernieres saisons.",
        "Verifier que les matches recents sont enregistres avant de calculer la performance.",
        "Contraster les nouveaux resultats avec les predictions pour identifier les ecarts.",
        "Alerte : toujours sauvegarder avant purge du cache pour eviter les pertes de donnees.",
        "Prompt IA : \"Quelles competitions manquent a l'import historique ?\"",
    ],
    "Joueurs": [
        "Lister les joueurs >200 minutes avec rating <6.5 pour suivi forme.",
        "Identifier absences ou blessures signalees dans la fiche equipe.",
        "Verifier coherence poste/minutes vs compositions recentes.",
        "Prompt IA : \"Quels joueurs risquent la rotation ou le repos cette journee ?\"",
    ],
    "Matchs": [
        "Filtrer la prochaine journee et signaler les rencontres live ou decalees.",
        "Comparer les derniers resultats FT avec les stats pour detecter des incoherences.",
        "Tester les filtres domicile/exterieur et sauvegarder les cas utiles.",
        "Prompt IA : \"Quel match a le plus gros ecart xG vs resultat sur la prochaine journee ?\"",
        "Prompt IA : \"Liste-moi les surprises potentielles (cotes >3.0) sur les matchs a venir.\"",
    ],
    "Passeurs": [
        "Identifier les meilleurs passeurs sur les 3 dernieres journees.",
        "Comparer assists domicile/exterieur pour reperer les tendances.",
        "Verifier les changements de role ou repositionnements recents.",
        "Prompt IA : \"Quel passeur a le meilleur ratio passes decisives/minutes ?\"",
    ],
    "Performance IA": [
        "Verifier le taux de reussite global et l'evolution recente.",
        "Analyser le tableau ROI/Edge par bookmaker pour prioriser les operateurs fiables.",
        "Exporter les 50 dernieres predictions pour analyse externe.",
        "Prompt IA : \"Comment evolue le ROI vs l'attendu sur le dernier mois ?\"",
    ],
    "Predictions": [
        "Choisir ligue/saison/equipe via la barre laterale.",
        "Comparer les probabilites 1X2 avec les cotes (page Bookmakers).",
        "Utiliser la note IA comme support, jamais comme conseil financier.",
        "Surveiller l'indice d'intensite (xG/Over/BTTS) et lire la synthese modele pour comprendre les drivers.",
        "Alerte : confirmer les compositions officielles avant de valider une prediction.",
        "Prompt IA : \"Quelle prediction presente le plus fort edge cette semaine ?\"",
    ],
    "Profil": [
        "Verifier que les alias bookmakers correspondent aux operateurs suivis.",
        "Mettre a jour le JSON apres ajout ou modification d'un bookmaker.",
        "Synchroniser les preferences avec le filtre de la page Bookmakers.",
        "Prompt IA : \"Quels parametres profil optimiser pour mon bankroll settings ?\"",
        "Prompt IA : \"Quels bookmakers surveiller selon mes favoris actuels ?\"",
    ],
    "Roadmap": [
        "Identifier les sections au-dessus de 60% reste et choisir le chantier prioritaire du jour.",
        "Noter les taches passees sous 30% pour cloture et preparation du changelog.",
        "Verifier la date de mise a jour par rapport au dernier deploy pour confirmer la fraicheur.",
        "Prompt IA : \"Priorise les 3 taches critiques restantes sur la roadmap.\"",
        "Prompt IA : \"Propose un plan sprint pour avancer de 10% sur la roadmap.\"",
    ],
    "Stades": [
        "Lister les stades >40k places pour les evenements majeurs.",
        "Verifier les villes et capacites pour les deplacements a venir.",
        "Identifier les stades partages entre plusieurs clubs.",
        "Prompt IA : \"Quels stades presenteront des conditions meteorologiques extremes ?\"",
    ],
    "Statistiques": [
        "Identifier les intervalles minute avec pics de buts pour l'equipe choisie.",
        "Comparer les moyennes buts pour/contre a la moyenne de la ligue.",
        "Exporter les graphiques pour le rapport hebdomadaire.",
        "Prompt IA : \"Analyse les statistiques offensives vs defensives de l'equipe X.\"",
        "Prompt IA : \"Ou se situent les faiblesses de l'equipe Y par rapport a la ligue ?\"",
    ],
    "Tableau IA": [
        "Consulter les cartes synthetiques (predictions totales, taux de reussite).",
        "Observer l'evolution du taux de succes et les edges par groupe de bookmakers.",
        "Identifier les top edges recents pour preparer la page Bookmakers.",
        "Prompt IA : \"Quel segment de bookmakers degrade la performance moyenne ?\"",
    ],
    "Tester l'API": [
        "Lancer les tests et noter les endpoints en echec ou trop lents.",
        "Verifier les quotas restants et les temps de reponse affiches.",
        "Documenter les erreurs pour les remonter au canal support.",
        "Prompt IA : \"Quels endpoints sont critiques pour la prochaine release ?\"",
    ],
}


def show_guides() -> None:
    st.header("Guides & Prompts")
    st.caption("Rappels rapides pour interroger l'IA et piloter chaque page.")

    for section, prompts in GUIDES.items():
        with st.expander(section, expanded=False):
            for prompt in prompts:
                st.write(f"- {prompt}")
            st.write(
                "Exemple prompt IA : "+
                f"\"Analyse {section.lower()} : que dois-je verifier en priorite aujourd'hui ?\""
            )

__all__ = ["show_guides"]






