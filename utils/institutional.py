from __future__ import annotations

import streamlit as st


def _section(title: str, body: list[str]) -> None:
    st.subheader(title)
    for paragraph in body:
        st.markdown(paragraph)


def show_access_governance() -> None:
    st.title("Acces et gouvernance")
    _section(
        "Principe d'acces restreint",
        [
            "L'environnement est accessible uniquement aux entites disposant d'un accord ecrit et en cours de validite.",
            "L'acces n'est jamais considere comme un droit acquis; il peut rester en attente ou ne jamais etre active.",
        ],
    )
    _section(
        "Audit continu et supervision",
        [
            "Chaque session, requete ou tentative d'action est tracee et exposee aux equipes de controle interne.",
            "Les journaux sont consultables a posteriori et peuvent declencher un blocage sans preavis.",
        ],
    )
    _section(
        "Responsabilite de l'utilisateur",
        [
            "Les utilisateurs conservent l'entier controle de leurs hypotheses et restent responsables des decisions prises ou refusees.",
            "Aucune delegation automatique n'est fournie; l'inaction demeure une issue licite.",
        ],
    )
    _section(
        "Suspension, refus, limitation",
        [
            "L'administrateur peut refuser, suspendre ou limiter un acces sans justification publique, notamment en cas de doute sur l'usage.",
            "Un acces partiel ou une suspension prolongee ne constitue pas un incident de service.",
        ],
    )
    _section(
        "Absence d'obligation de service",
        [
            "Aucun engagement de disponibilite ou de reponse n'est garanti.",
            "Le dispositif peut rester silencieux si les conditions minimales ne sont pas reunies.",
        ],
    )


def show_methodology_limits() -> None:
    st.title("Methodologie et limites")
    _section(
        "Nature probabiliste des sorties",
        [
            "Les resultats expriment des probabilites conditionnelles, sans certitude ni horizon fixe.",
            "Les plages d'incertitude peuvent conduire a des sorties neutres ou vides.",
        ],
    )
    _section(
        "Structuration vs prediction",
        [
            "Le systeme organise les donnees utiles pour cadrer une decision; il ne predit ni score ni issue finale.",
            "La phrase de reference reste: structurer la decision, pas predire le resultat.",
        ],
    )
    _section(
        "Filtres et blocage",
        [
            "Des filtres successifs peuvent bloquer toute recommandation lorsque les seuils de confiance sont insuffisants.",
            "Un blocage n'est pas une erreur; il rappelle que ne rien faire est acceptable.",
        ],
    )
    _section(
        "Limites connues et assumees",
        [
            "Les donnees sources sont imparfaites, partiellement ajournees et sujettes a retraction.",
            "Aucune correction automatique n'est promise; les zones grises sont signalees puis laissees a l'appreciation humaine.",
        ],
    )
    _section(
        "Responsabilite humaine finale",
        [
            "Toute decision, action ou refus appartient a l'utilisateur mandate.",
            "Aucun scenario genere ne constitue une consigne; l'utilisateur peut interrompre le processus a tout moment.",
        ],
    )


def show_security_data() -> None:
    st.title("Securite et donnees")
    _section(
        "Hebergement et infrastructure",
        [
            "Le systeme repose sur une infrastructure geree et auditee de maniere reguliere.",
            "Les composants critiques sont isoles sur des environnements controles et journalises.",
        ],
    )
    _section(
        "Chiffrement en transit et au repos",
        [
            "Les flux reseau sont proteges par chiffrement standardise.",
            "Les donnees stockees sont chiffrees; l'acces physique ou logique necessite une double validation.",
        ],
    )
    _section(
        "Journalisation et tracabilite",
        [
            "Les operations sensibles font l'objet d'une journalisation horodatee.",
            "Ces journaux sont conserves pour reference et peuvent bloquer de nouvelles operations.",
        ],
    )
    _section(
        "Separation donnees et moteur",
        [
            "Les donnees brutes, les traitements et les interfaces sont heberges sur des couches distinctes.",
            "Une panne d'un composant n'entraine pas automatiquement l'arret des autres.",
        ],
    )
    _section(
        "Confidentialite et non partage",
        [
            "Les donnees client ne sont pas revendues ni partagees en dehors des obligations legales.",
            "En l'absence d'ordre formel, aucune extraction automatique n'est effectuee.",
        ],
    )


def show_legal_responsibility() -> None:
    st.title("Mentions legales et responsabilite")
    _section(
        "Mentions legales",
        [
            "L'environnement est edite par une entite identifiee dans les contrats transmis aux utilisateurs autorises.",
            "Les coordonnees completes sont disponibles sur demande ecrite.",
        ],
    )
    _section(
        "Limitation de responsabilite",
        [
            "Les informations diffusees sont fournies en l'etat, sans garantie de continuite ni d'exactitude totale.",
            "L'editeur ne peut etre tenu responsable d'une interpretation erronee ou d'un usage hors cadre.",
        ],
    )
    _section(
        "Absence de conseil financier",
        [
            "Aucune fonctionnalite ne constitue un conseil financier, juridique ou de paris sportifs.",
            "Toute decision d'investissement ou de mise est hors du perimetre du systeme.",
        ],
    )
    _section(
        "Usage sous responsabilite exclusive",
        [
            "L'utilisateur agre que l'utilisation, l'interruption ou l'inaction relevent de sa seule responsabilite.",
            "Aucune delegation ni mandat implicite n'est emis par la plateforme.",
        ],
    )
    _section(
        "Droit applicable et juridiction",
        [
            "Le dispositif est soumis au droit applicable precise dans les contrats cadres.",
            "Tout litige sera porte devant la juridiction competente designee dans ces accords.",
        ],
    )
