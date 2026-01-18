import pandas as pd
import re
from typing import Optional, Tuple

df = pd.read_csv("data/prediction_history.csv")


def _parse_score(row: pd.Series) -> Tuple[Optional[int], Optional[int]]:
    score_str = str(row.get("result_score", "")).strip()
    if not score_str or score_str.lower() == "nan":
        return None, None
    match = re.match(r"(\d+)-(\d+)", score_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def _normalize_winner(value: str) -> str:
    val = str(value).strip().lower()
    if val in {"home", "domicile", "1"}:
        return "home"
    if val in {"away", "extérieur", "exterieur", "2"}:
        return "away"
    if val in {"draw", "nul", "x"}:
        return "draw"
    return ""


def _selection_success(
    selection: str,
    winner: str,
    home_goals: Optional[int],
    away_goals: Optional[int],
    home_name: Optional[str],
    away_name: Optional[str],
) -> Optional[bool]:
    if not selection or not winner or home_goals is None or away_goals is None:
        return None

    selection = str(selection).lower().strip()
    winner = str(winner).lower().strip()
    home_name = str(home_name or "").lower().strip()
    away_name = str(away_name or "").lower().strip()

    total_goals = home_goals + away_goals

    # Over/Under
    if "over" in selection and "2.5" in selection:
        return total_goals > 2
    if "under" in selection and "2.5" in selection:
        return total_goals <= 2
    if "over" in selection and "1.5" in selection:
        return total_goals > 1
    if "under" in selection and "1.5" in selection:
        return total_goals <= 1

    # BTTS
    if "btts" in selection or "deux" in selection and "équipes" in selection:
        both = home_goals > 0 and away_goals > 0
        if "non" in selection or "non" in selection:
            return not both
        return both

    # Victoire domicile
    if "victoire" in selection and home_name and home_name in selection:
        return home_goals > away_goals
    if "victoire" in selection and away_name and away_name in selection:
        return away_goals > home_goals
    if "victoire" in selection:
        result = _normalize_winner(winner)
        return result == "home"

    # Double chance
    if "1x" in selection or "double chance 1x" in selection:
        return home_goals >= away_goals
    if "x2" in selection or "double chance x2" in selection:
        return away_goals >= home_goals
    if "12" in selection or "double chance 12" in selection:
        return home_goals != away_goals

    return None


def _first_valid_selection(*candidates):
    for c in candidates:
        if c and str(c).strip() and str(c).lower() != "nan":
            return str(c).strip()
    return ""


def _prediction_side(row: pd.Series) -> Optional[str]:
    main_pick = str(row.get("main_pick", "")).lower()
    if any(x in main_pick for x in {"victoire", "domicile", "home", "1"}):
        return "home"
    if any(x in main_pick for x in {"nul", "draw", "x"}):
        return "draw"
    if any(x in main_pick for x in {"away", "extérieur", "exterieur", "2"}):
        return "away"
    return None


def _compute_success(row: pd.Series) -> Optional[bool]:
    result = str(row.get("result_winner", ""))
    selection = _first_valid_selection(
        row.get("bet_selection"),
        row.get("total_pick"),
        row.get("main_pick"),
    )
    home_goals, away_goals = _parse_score(row)
    selection_result = _selection_success(
        selection,
        result,
        home_goals,
        away_goals,
        row.get("home_team"),
        row.get("away_team"),
    )
    if selection and selection_result is not None:
        return selection_result
    if not result:
        return None
    side = _prediction_side(row)
    if not side:
        return None
    result_norm = _normalize_winner(result)
    if not result_norm:
        return None
    if result_norm == "home":
        return side == "home"
    if result_norm == "away":
        return side == "away"
    if result_norm == "draw":
        return side == "draw"
    return None


# Appliquer la logique
df["success"] = df.apply(_compute_success, axis=1)

# Analyser
completed = df[df["success"].notna()]
print(f"✅ Prédictions finalisées: {len(completed)}")
print(f"🎯 Succès calculé: {completed['success'].astype(bool).sum()}")
print(f"📊 Win rate RÉEL: {completed['success'].mean() * 100:.1f}%")

print("\nExemples de prédictions réussies:")
print(
    completed[completed["success"] == True][
        ["home_team", "away_team", "main_pick", "result_score", "result_winner"]
    ].head(10)
)
