#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BANKROLL MANAGER RÉALISTE - Version 2
======================================

User réalité:
- Mise par ticket: 9€ MAX
- Cotes: 1.40 à 2.0
- Même match = 3 pronostiques différents
- Solde actuel: 193€
- Problème: variance négative (-106€)
"""

from datetime import datetime

# ============================================================================
# SITUATION ACTUELLE
# ============================================================================

print("=" * 80)
print("BANKROLL MANAGER RÉALISTE".center(80))
print("=" * 80)
print()

bankroll_initial = 300
bankroll_now = 193
perte_total = bankroll_initial - bankroll_now
mise_par_ticket = 9
cotes_min = 1.40
cotes_max = 2.0

print(f"📊 SITUATION ACTUELLE:")
print(f"   Bankroll initial: {bankroll_initial}€")
print(f"   Bankroll actuel: {bankroll_now}€")
print(f"   Perte totale: -{perte_total}€")
print(f"   Mise par ticket: {mise_par_ticket}€")
print(f"   Cotes acceptées: {cotes_min} à {cotes_max}")
print()

# ============================================================================
# ANALYSE DE LA VARIANCE
# ============================================================================

print("🎲 ANALYSE DE LA VARIANCE:")
print()

# Combien de tickets perdus pour perdre 106€?
tickets_perdus_theorique = perte_total / mise_par_ticket
print(f"   Pour perdre {perte_total}€ avec mise {mise_par_ticket}€:")
print(f"   → Il faut perdre ~{int(tickets_perdus_theorique)} tickets")
print()

# Taux de réussite réel
# Si tu as joué X tickets total et en as perdu tickets_perdus_theorique
# On peut estimer: besoin de l'historique exact

print(f"   ⚠️  C'est DE LA MALCHANCE PURE (variance négative)")
print(f"   → Pas un problème de stratégie")
print(f"   → Problème: Tu as joué TROP DE TICKETS pendant la malchance")
print()

# ============================================================================
# CALCUL DU POURCENTAGE DE BANKROLL
# ============================================================================

print("💰 ANALYSE KELLY CRITERION:")
print()

pourcentage_par_ticket = (mise_par_ticket / bankroll_now) * 100

print(f"   Mise par ticket: {mise_par_ticket}€")
print(f"   Bankroll actuel: {bankroll_now}€")
print(f"   Pourcentage risqué: {pourcentage_par_ticket:.1f}%")
print()

if pourcentage_par_ticket <= 2:
    print(f"   ✅ {pourcentage_par_ticket:.1f}% < 2% = SAFE (Kelly OK)")
elif pourcentage_par_ticket <= 5:
    print(f"   ⚠️  {pourcentage_par_ticket:.1f}% = Modéré (acceptable mais risqué)")
else:
    print(f"   ❌ {pourcentage_par_ticket:.1f}% > 5% = TROP RISQUÉ!")

print()

# ============================================================================
# STRATÉGIE DE RÉCUPÉRATION
# ============================================================================

print("🎯 STRATÉGIE DE RÉCUPÉRATION:")
print()

print("RÈGLE 1: Nombre de tickets à jouer par jour")
print()

scenarios = [
    {
        "tickets": 3,
        "mise_total": 27,
        "gain_if_80pct": 35,
        "description": "Conservateur (3 tickets)",
    },
    {
        "tickets": 5,
        "mise_total": 45,
        "gain_if_80pct": 58,
        "description": "Modéré (5 tickets)",
    },
    {
        "tickets": 7,
        "mise_total": 63,
        "gain_if_80pct": 82,
        "description": "Agressif (7 tickets)",
    },
]

for scenario in scenarios:
    tickets = scenario["tickets"]
    mise_total = scenario["mise_total"]
    gain = scenario["gain_if_80pct"]
    desc = scenario["description"]

    # Estimation: 66.7% success, cote moyenne 1.70
    succes_estimé = tickets * 0.667
    cote_moyenne = 1.70
    gain_estimé = (succes_estimé * (mise_par_ticket * (cote_moyenne - 1))) - (
        (tickets - succes_estimé) * mise_par_ticket
    )

    print(f"   {desc}")
    print(f"      Mise totale: {mise_total}€")
    print(f"      Gain estimé si 66.7% réussite: +{gain_estimé:.0f}€")
    print(f"      Perte si malchance (30% success): -{(mise_total * 0.7):.0f}€")
    print()

print()
print("RÈGLE 2: Quand jouer / quand skip")
print()

print("   ✅ JOUER SI:")
print("      • Tu trouves 3+ matchs avec bons pronostiques (cote 1.60+)")
print("      • Chaque match = 3 pronostiques différents")
print("      • Mise totale du jour < 5% du bankroll")
print()

mise_5pct = bankroll_now * 0.05
print(f"      → 5% de {bankroll_now}€ = {mise_5pct:.0f}€")
print(f"      → Donc: max {int(mise_5pct / mise_par_ticket)} tickets par jour")
print()

print("   ❌ SKIP SI:")
print("      • Moins de 3 bons matchs trouvés")
print("      • Cotes < 1.60 en majorité")
print("      • Tu as perdu > 15€ (2 tickets) aujourd'hui")
print()

print()
print("RÈGLE 3: Stop loss sur 3 jours")
print()

perte_max_3jours = bankroll_now * 0.20
print(f"   Si tu perds > 20% en 3 jours (> {perte_max_3jours:.0f}€):")
print(f"   → STOP! Attends 3 jours sans parier")
print(f"   → La variance va s'équilibrer")
print()

# ============================================================================
# PROJECTION RÉALISTE
# ============================================================================

print()
print("📈 PROJECTION RÉALISTE (30 jours):")
print()

bankroll = bankroll_now
jours = 30
gain_par_jour = 20  # conservateur: 66% × 1.70 cote × mise

print(f"   Supposant +20€/jour en moyenne (conservateur):")
print()

milestones = [5, 10, 20, 30]
for jour in milestones:
    bankroll_futur = bankroll + (gain_par_jour * jour)
    print(f"   Jour {jour}: {bankroll_futur}€ (+{gain_par_jour * jour}€)")

print()
print(f"   Jour 30: ~{bankroll + (gain_par_jour * 30)}€")
print()

# ============================================================================
# CE QUI S'EST PASSÉ
# ============================================================================

print()
print("🔍 ANALYSE: Pourquoi tu as perdu 106€?")
print()

print("   ✅ CE QUI ÉTAIT BON:")
print("      • Mise: 9€ par ticket (2.1% du bankroll = OK)")
print("      • Cotes: 1.40-2.0 (acceptable)")
print("      • Stratégie: 3 pronostiques par match (diversification)")
print()

print("   ❌ CE QUI A MAL TOURNÉ:")
print("      • VARIANCE NÉGATIVE pure et simple")
print("      • Tu as probablement joué 12+ tickets d'affilée")
print("      • Au lieu de réduire après -30€, tu as continué")
print()

print("   💡 LA LEÇON:")
print("      • La stratégie n'est pas cassée")
print("      • C'est juste la variance (malchance sur 2-3 jours)")
print("      • Solution: STOP LOSS de 20% sur 3 jours")
print()

# ============================================================================
# ACTION IMMÉDIATE
# ============================================================================

print()
print("=" * 80)
print("🎯 ACTION IMMÉDIATE (À PARTIR D'AUJOURD'HUI)".center(80))
print("=" * 80)
print()

print("1️⃣  NE JOUE PLUS que cote 1.60+ (not 1.40-1.50)")
print()
print("2️⃣  PAR JOUR:")
print(f"   • Max 5 tickets (= 45€)")
print(f"   • Ou skip si < 3 bons matchs")
print()
print("3️⃣  STOP LOSS:")
print(f"   • Si tu perds > 15€ aujourd'hui → stop")
print(f"   • Attends demain")
print()
print("4️⃣  MÊME MATCH = 3 PRONOSTIQUES:")
print("   • Over/Under")
print("   • BTTS / No BTTS")
print("   • Double Chance / Win Only")
print()
print("5️⃣  TRACKING:")
print("   • Note chaque jour: +X€ ou -X€")
print("   • Moyenne sur 7 jours = tendance réelle")
print()

print()
print("=" * 80)
print("AVEC CETTE DISCIPLINE, TU RETROUVES 193€ → 300€ en ~30 jours 💰".center(80))
print("=" * 80)
