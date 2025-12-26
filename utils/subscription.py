from __future__ import annotations

from typing import Dict, Optional

PLAN_LEVELS: Dict[str, int] = {
    "lite": 0,
    "starter": 1,
    "pro": 2,
    "elite": 3,
}

PLAN_LABELS: Dict[str, str] = {
    "lite": "Starter Lite",
    "starter": "Starter",
    "pro": "Proba Edge Pro",
    "elite": "Elite",
}

DEFAULT_PLAN = "lite"
UPGRADE_URL = "mailto:contact@probaedge.ai?subject=Upgrade%20ProbaEdge"
PLAN_CODES = list(PLAN_LEVELS.keys())

MENU_REQUIREMENTS: Dict[str, Optional[str]] = {
    "Predictions": "starter",
    "Profil": "starter",
    "Historique": "starter",
    "Roadmap": "starter",
    "Rapports": "starter",
    "Assistant IA": "pro",
    "Performance IA": "pro",
    "Tableau IA": "pro",
    "Supervision": "pro",
    "Tester l'API": "pro",
    "Audit interne": "pro",
    "Admin": "elite",
}

COACH_MIN_PLAN = "pro"


def normalize_plan(plan: Optional[str]) -> str:
    code = (plan or "").strip().lower()
    return code if code in PLAN_LEVELS else DEFAULT_PLAN


def plan_label(plan: Optional[str]) -> str:
    code = normalize_plan(plan)
    return PLAN_LABELS.get(code, PLAN_LABELS[DEFAULT_PLAN])


def plan_allows(plan: Optional[str], required: Optional[str]) -> bool:
    if required is None:
        return True
    plan_code = normalize_plan(plan)
    required_code = normalize_plan(required)
    return PLAN_LEVELS[plan_code] >= PLAN_LEVELS[required_code]


def menu_required_plan(menu: str) -> Optional[str]:
    return MENU_REQUIREMENTS.get(menu)


def format_upgrade_hint(current_plan: Optional[str], required_plan: Optional[str]) -> str:
    current = plan_label(current_plan)
    required = plan_label(required_plan)
    return (
        f"Plan actuel : **{current}**. Cette fonctionnalitÃ© est disponible Ã\xa0 partir de **{required}**.\n\n"
        "Consultez l'onglet *Offres & abonnements* ou contactez-nous pour mettre Ã\xa0 niveau votre compte."
    )


__all__ = [
    "PLAN_CODES",
    "PLAN_LEVELS",
    "PLAN_LABELS",
    "DEFAULT_PLAN",
    "MENU_REQUIREMENTS",
    "COACH_MIN_PLAN",
    "normalize_plan",
    "plan_label",
    "plan_allows",
    "menu_required_plan",
    "format_upgrade_hint",
    "UPGRADE_URL",
]
