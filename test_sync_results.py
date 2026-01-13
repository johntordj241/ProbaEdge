#!/usr/bin/env python3
"""
Test rapide pour vérifier que la synchronisation des résultats fonctionne.
"""

from utils.prediction_history import load_prediction_history, sync_prediction_results

print("=" * 60)
print("🔍 TEST DE SYNCHRONISATION DES RÉSULTATS")
print("=" * 60)

# Charger l'historique actuel
df = load_prediction_history()
print(f"\n📊 Historique chargé: {len(df)} lignes")

# Compter les matchs en attente
pending_mask = (df["result_status"].isna()) | (df["result_status"] == "")
pending_count = pending_mask.sum()
print(f"⏳ Matchs en attente de résultat: {pending_count}")

if pending_count > 0:
    pending_df = df[pending_mask][
        ["timestamp", "home_team", "away_team", "fixture_date", "result_status"]
    ].head(10)
    print("\n📋 Premiers matchs en attente:")
    print(pending_df.to_string())

# Lancer la synchronisation
print("\n🔄 Lancement de la synchronisation...")
try:
    synced = sync_prediction_results(limit=100)
    print(f"✅ {synced} matchs synchronisés avec succès!")
except Exception as e:
    print(f"❌ Erreur lors de la synchronisation: {e}")

# Recharger et vérifier
print("\n🔍 Vérification après synchronisation...")
df_after = load_prediction_history()
pending_after = (
    (df_after["result_status"].isna()) | (df_after["result_status"] == "")
).sum()
print(f"⏳ Matchs en attente (après): {pending_after}")

if pending_count > pending_after:
    print(f"✅ {pending_count - pending_after} matchs ont été mis à jour!")
else:
    print("ℹ️  Aucune mise à jour détectée (les résultats étaient déjà à jour)")

print("\n" + "=" * 60)
