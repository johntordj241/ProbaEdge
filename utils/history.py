from pathlib import Path
import csv
from typing import List, Dict, Any

HISTORIQUE_PATH = Path('data/historique.csv')
HEADER = [
    "fixture_id",
    "league_id",
    "season",
    "date",
    "home_team_id",
    "home_team",
    "away_team_id",
    "away_team",
    "status",
    "goals_home",
    "goals_away",
]

def load_history() -> List[Dict[str, Any]]:
    if not HISTORIQUE_PATH.exists():
        return []
    with HISTORIQUE_PATH.open('r', encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def save_history(rows: List[Dict[str, Any]]) -> None:
    HISTORIQUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORIQUE_PATH.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)

__all__ = ["load_history", "save_history", "HEADER", "HISTORIQUE_PATH"]
