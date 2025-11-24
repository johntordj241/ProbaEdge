# utils/data.py
from datetime import datetime

# Mapping des ligues vers les IDs API
league_mapping = {
    "Ligue 1 (France)": 61,
    "Premier League (Angleterre)": 39,
    "La Liga (Espagne)": 140,
    "Serie A (Italie)": 135,
    "Bundesliga (Allemagne)": 78,
    "Champions League (Europe)": 2,
    "Europa League": 3,
    "Euro (Europe)": 4,
    "Coupe du Monde (FIFA)": 1,
}

# Liste des saisons supportées
seasons_available = [2023, 2024, 2025]

def get_current_season() -> int:
    """Retourne la saison courante automatiquement."""
    year = datetime.now().year
    return year if year in seasons_available else max(seasons_available)

