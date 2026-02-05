import pandas as pd
from pathlib import Path
from datetime import datetime

# Paramètres
DATE = None  # Mets ici une date au format 'YYYY-MM-DD' pour filtrer une journée précise, sinon None pour tout

# Fichier d'historique
history_file = Path("data/prediction_history.csv")
if not history_file.exists():
    print("❌ prediction_history.csv not found")
    exit(1)

df = pd.read_csv(history_file)

# On suppose qu'il y a une colonne 'ticket_id' (ou 'bet_id') pour regrouper les tickets combinés
# Si tu n'as pas cette colonne, chaque ligne = 1 ticket simple
if "ticket_id" not in df.columns:
    df["ticket_id"] = df.index  # chaque ligne = 1 ticket unique

# Filtrer par date si besoin
if "fixture_date" in df.columns:
    df["fixture_date"] = pd.to_datetime(df["fixture_date"], errors="coerce", utc=True)
    if DATE:
        mask = df["fixture_date"].dt.strftime("%Y-%m-%d") == DATE
        df = df[mask]

# Pour chaque ticket, on regarde si TOUS les paris sont gagnants
# On considère 'result_winner' == 'yes' ou 'win' ou 'correct' comme gagnant


def is_ticket_won(ticket_df):
    results = ticket_df["result_winner"].astype(str).str.lower().values
    return all(r in ["yes", "win", "correct"] for r in results)


tickets = df.groupby("ticket_id")

total = tickets.ngroups
won = sum(is_ticket_won(ticket) for _, ticket in tickets)

print(f"Total tickets joués : {total}")
print(f"Tickets gagnés : {won}")
if total > 0:
    print(f"Taux de réussite : {won/total*100:.1f}%")
else:
    print("Aucun ticket trouvé.")

# Détail des tickets perdus (optionnel)
print("\nTickets perdus :")
for tid, ticket in tickets:
    if not is_ticket_won(ticket):
        print(f"Ticket {tid} :")
        print(
            ticket[
                ["fixture_date", "home_team", "away_team", "main_pick", "result_winner"]
            ]
        )
        print("-")
