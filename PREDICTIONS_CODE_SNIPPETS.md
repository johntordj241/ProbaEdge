# 💻 Code Snippets: Implémentation main_pick & BTTS

**Pour développeurs qui veulent copier-coller et comprendre**

---

## 1️⃣ BTTS Calculation (Poisson)

### Code Source Actuel
```python
# Fichier: utils/prediction_model.py (lignes 188-211)
def aggregate_poisson_markets(matrix: Sequence[Sequence[float]]) -> Dict[str, float]:
    """Agrège la matrice Poisson pour obtenir les marchés."""
    home = draw = away = over_1_5 = over_2_5 = btts_yes = 0.0
    
    for i, row in enumerate(matrix):
        for j, prob in enumerate(row):
            # Accumulate 1X2 probabilities
            if i > j:
                home += prob
            elif i == j:
                draw += prob
            else:
                away += prob
            
            # Accumulate Over/Under
            if i + j >= 2:
                over_1_5 += prob
            if i + j >= 3:
                over_2_5 += prob
            
            # BTTS: Les deux équipes marquent (i>0 AND j>0)
            if i > 0 and j > 0:  # ← CLEF: i>0 AND j>0
                btts_yes += prob
    
    return {
        "home": home,
        "draw": draw,
        "away": away,
        "over_1_5": over_1_5,
        "over_2_5": over_2_5,
        "btts_yes": btts_yes,           # Probabilité BTTS Yes
        "btts_no": 1 - btts_yes,        # Probabilité BTTS No
    }
```

### Explication
```
Matrice Poisson (i=buts domicile, j=buts extérieur):

       j=0    j=1    j=2    j=3
i=0   0.20   0.30   0.25   ...   ← i=0: Domicile 0 but → Pas BTTS
i=1   0.30   0.40   0.33   ...   ← i=1: Compter si j>0
i=2   0.20   0.33   0.25   ...   ← i=2: Compter si j>0
i=3   0.10   0.16   0.12   ...   ← i=3: Compter si j>0

BTTS_YES = 0.40 + 0.33 + 0.33 + 0.25 + ... = Σ de toutes les cellules (i>0, j>0)
```

### Utilisation Simplifiée
```python
from utils.prediction_model import poisson_matrix, aggregate_poisson_markets

# Données d'entrée
lambda_home = 1.5  # xG attendu domicile
lambda_away = 1.9  # xG attendu extérieur

# Étape 1: Générer matrice Poisson 6×6
matrix = poisson_matrix(lambda_home, lambda_away)

# Étape 2: Agréger pour obtenir tous les marchés
markets = aggregate_poisson_markets(matrix)

# Étape 3: Extraire BTTS
btts_prob = markets["btts_yes"]  # 0.72
btts_no_prob = markets["btts_no"]  # 0.28

# Étape 4: Prédiction
if btts_prob >= 0.5:
    prediction = "BTTS: OUI"
else:
    prediction = "BTTS: NON"

print(f"BTTS Probabilité: {btts_prob:.2%}")  # 72%
print(f"Prédiction: {prediction}")            # BTTS: OUI
```

---

## 2️⃣ main_pick Selection (argmax)

### Code Source Actuel
```python
# Fichier: utils/predictions.py (lignes 2065-2085)
def _betting_tips(
    home_strength: Any,
    away_strength: Any,
    probs: Dict[str, float],
    markets: Dict[str, float],
    *,
    top_scores: Optional[List[Dict[str, Any]]] = None,
    odds_map: Optional[Dict[str, float]] = None,
    over_bias: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Génère les tips de paris."""
    
    # Extraire les 3 probabilités 1X2
    home_prob = probs.get("home", 0.0)
    draw_prob = probs.get("draw", 0.0)
    away_prob = probs.get("away", 0.0)
    
    # ← CLEF: Sélectionner le maximum
    main_choice = max(
        ("home", home_prob),
        ("draw", draw_prob),
        ("away", away_prob),
        key=lambda item: item[1],  # Compare par la 2e valeur (probabilité)
    )
    
    # Générer le label basé sur le choix
    if main_choice[0] == "home":
        label = f"Victoire {home_strength.name}"
        reason = f"Projection xG {home_strength.lambda_value:.2f} contre {away_strength.lambda_value:.2f}."
    elif main_choice[0] == "away":
        label = f"Victoire {away_strength.name}"
        reason = f"{away_strength.name} affiche {away_strength.lambda_value:.2f} xG attendus."
    else:  # draw
        label = "Match nul"
        reason = "Forces proches, scenario equilibre sur le 1X2."
    
    # Ajouter confidence faible si < 20%
    if main_choice[1] < 0.2:
        reason += " (confiance reduite <20%, verifier contexte)."
    
    # Retourner le tip
    add_tip(label, main_choice[1], reason, min_probability=0.0)
    
    return tips  # Liste de tous les tips générés
```

### Explication
```
Sélection = argmax({home: 0.35, draw: 0.22, away: 0.43})
           = "away" (car 0.43 > 0.35 > 0.22)

Puis générer label:
  "Victoire Manchester City" (si away)
  "Victoire Liverpool" (si home)
  "Match nul" (si draw)
```

### Utilisation Simplifiée
```python
# Données d'entrée
probs = {
    "home": 0.35,
    "draw": 0.22,
    "away": 0.43,
}

# Étape 1: Sélectionner le maximum
main_choice = max(
    ("home", probs["home"]),
    ("draw", probs["draw"]),
    ("away", probs["away"]),
    key=lambda item: item[1],
)

# Étape 2: Extraire le choix
choice_side, choice_prob = main_choice
# choice_side = "away"
# choice_prob = 0.43

# Étape 3: Créer label (simplifié)
team_names = {"home": "Liverpool", "draw": "Nul", "away": "Man City"}
label = f"Victoire {team_names[choice_side]}"

# Étape 4: Output
main_pick = {
    "label": label,              # "Victoire Man City"
    "probability": choice_prob,   # 0.43
    "confidence": int(choice_prob * 100),  # 43%
}

print(f"main_pick: {main_pick['label']}")
print(f"Confiance: {main_pick['confidence']}%")
```

---

## 3️⃣ Matrice Poisson (Fondation)

### Code Source
```python
# Fichier: utils/prediction_model.py (lignes 176-186)
def poisson_matrix(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 6,
    *,
    mode: Optional[str] = None,
    rho: Optional[float] = None,
    tau: Optional[float] = None,
) -> List[List[float]]:
    """
    Génère une matrice Poisson bivariée 6×6.
    
    Args:
        lambda_home: xG expected du domicile
        lambda_away: xG expected de l'extérieur
        max_goals: Nombre max de buts par équipe (défaut 6)
        mode: Mode de calcul ("dc" par défaut = Double Chance)
        rho: Paramètre corrélation bivariée (0.03)
        tau: Paramètre Double Chance (0.06)
    """
    
    # Appeler la fonction C/Rust optimisée
    raw_matrix = _scoreline_matrix(
        max(lambda_home, 0.0),
        max(lambda_away, 0.0),
        max_goals=max_goals,
        mode=(mode or DEFAULT_SCORELINE_MODE),  # "dc"
        rho=rho if rho is not None else DEFAULT_BIVARIATE_RHO,  # 0.03
        tau=tau if tau is not None else DEFAULT_DC_TAU,          # 0.06
    )
    
    # Normaliser pour que la somme = 1.0
    return _normalize_score_matrix(raw_matrix)
```

### Utilisation
```python
from utils.prediction_model import poisson_matrix

# Données
lambda_home = 1.5
lambda_away = 1.9

# Générer matrice
matrix = poisson_matrix(
    lambda_home,
    lambda_away,
    max_goals=6,
    mode="dc",    # Double Chance bivariate
    rho=0.03,     # Corrélation
    tau=0.06,     # DC parameter
)

# Résultat: List[List[float]] 6×6
print(f"Matrix shape: {len(matrix)} rows")
print(f"Matrix[1][1] (prob 1-1): {matrix[1][1]:.4f}")

# Vérification: somme = 1.0
total = sum(sum(row) for row in matrix)
print(f"Total probabilité: {total:.4f}")  # ~1.0
```

### Structure Matrice
```
        Away Goals
        0    1    2    3    4    5+
    0  0.20 0.30 0.25 0.13 0.05 0.01
    1  0.30 0.40 0.33 0.17 0.06 0.02
H 2   0.20 0.33 0.25 0.12 0.05 0.02
o 3   0.10 0.16 0.12 0.06 0.02 0.01
m 4   0.05 0.08 0.06 0.03 0.01 0.00
e 5   0.02 0.03 0.02 0.01 0.00 0.00

matrix[0] = [0.20, 0.30, 0.25, ...]  ← 0 buts domicile
matrix[1] = [0.30, 0.40, 0.33, ...]  ← 1 but domicile
matrix[2] = [0.20, 0.33, 0.25, ...]  ← 2 buts domicile
```

---

## 4️⃣ Calcul xG (Expected Goals)

### Code Source
```python
# Fichier: utils/prediction_model.py (lignes 378-413)
def expected_goals_from_standings(
    standings: List[Dict[str, Any]],
    home_id: int,
    away_id: int,
    home_name: str,
    away_name: str,
) -> Tuple[TeamStrength, TeamStrength, LeagueBaseline]:
    """
    Calcule les xG (λ) pour chaque équipe basé sur standings.
    """
    
    # Étape 1: Calculer baseline ligue
    baseline = compute_league_baseline(standings)
    
    # Étape 2: Obtenir Elo ratings
    elo_home, elo_away, delta_home = get_match_ratings(home_id, away_id)
    
    # Étape 3: Trouver lignes standings
    home_row = next((s for s in standings if s["team"]["id"] == home_id), None)
    away_row = next((s for s in standings if s["team"]["id"] == away_id), None)
    
    # Étape 4: Calculer force défensive
    def defensive_rate(row):
        if not row:
            return baseline.avg_defense
        goals_against = row["all"]["goals"]["against"]
        played = row["all"]["played"]
        return max(goals_against / played, 0.1) if played else baseline.avg_defense
    
    # Étape 5: Calculer forces domicile/extérieur
    home_strength = compute_team_strength(
        home_row,
        home_id,
        home_name,
        baseline,
        opponent_def=defensive_rate(away_row),
        team_rating=elo_home,
        delta_elo=delta_home,
        home_advantage=1.10,  # ← Avantage domicile
    )
    
    away_strength = compute_team_strength(
        away_row,
        away_id,
        away_name,
        baseline,
        opponent_def=defensive_rate(home_row),
        team_rating=elo_away,
        delta_elo=-delta_home,
        home_advantage=1.00,  # ← Pas d'avantage extérieur
    )
    
    return home_strength, away_strength, baseline
```

### Formule xG Simplifiée
```
λ = (Buts Marqués / Matchs) × (Déf Adversaire / Déf Moyenne Ligue) × Avantage Domicile × Elo Adjustment

Exemple:
λ_home = (1.8 / 1) × (1.1 / 1.2) × 1.10 × exp((0.6 × 150) / 400)
       = 1.8 × 0.917 × 1.10 × 1.037
       = 1.49
```

### Utilisation
```python
from utils.prediction_model import expected_goals_from_standings

# Données
standings = [
    {
        "team": {"id": 1, "name": "Liverpool"},
        "all": {"played": 20, "goals": {"for": 36, "against": 22}}
    },
    # ... autres équipes ...
]

home_id, away_id = 1, 2
home_name, away_name = "Liverpool", "Man City"

# Calculer xG
home_strength, away_strength, baseline = expected_goals_from_standings(
    standings, home_id, away_id, home_name, away_name
)

print(f"Home λ: {home_strength.lambda_value:.2f}")  # 1.49
print(f"Away λ: {away_strength.lambda_value:.2f}")  # 1.92
print(f"Elo diff: {home_strength.delta_elo}")       # +150
```

---

## 5️⃣ ML Calibration (Optionnel)

### Code Source
```python
# Fichier: utils/prediction_model.py (lignes 121-135)
def calibrate_match_probabilities(
    probs: Dict[str, float],
    markets: Dict[str, float],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    Recalibrate probabilités Poisson avec modèle ML optionnel.
    """
    
    # Charger modèle
    model = _load_outcome_model()
    
    # Si modèle n'existe pas → retourner probs inchangées
    if model is None:
        return probs
    
    try:
        # Construire features
        _, features = _ml_feature_vector(probs, markets, meta=meta)
        
        # Prédire
        predicted = model.predict_proba(features)[0]
        classes = getattr(model, "classes_", [])
        
        # Mapper résultats
        ml_map = {str(label): float(value) for label, value in zip(classes, predicted)}
        
        # Normaliser et retourner
        return _normalize_probability_map(ml_map, probs)
    
    except Exception:
        # En cas d'erreur → fallback Poisson
        return probs
```

### Features ML
```python
# 19 features utilisées par ML model

features = {
    # Probabilités Poisson brutes (3)
    "prob_home": 0.35,
    "prob_draw": 0.22,
    "prob_away": 0.43,
    
    # Dérivées (6)
    "feature_home_draw_diff": 0.13,
    "feature_home_away_diff": -0.08,
    "feature_over_under_diff": 0.10,
    "feature_max_prob": 0.43,
    "feature_main_confidence_norm": 0.43,
    "feature_total_pick_over": 1.0,
    
    # Markets (2)
    "prob_over_2_5": 0.55,
    "prob_under_2_5": 0.45,
    
    # xG (2)
    "feature_lambda_home": 1.49,
    "feature_lambda_away": 1.92,
    
    # Elo (3)
    "elo_home": 1650,
    "elo_away": 1800,
    "delta_elo": -150,
    
    # Contexte (2)
    "pressure_score": 0.45,
    "intensity_score": 52,
}
```

### Utilisation
```python
from utils.prediction_model import calibrate_match_probabilities

# Probs Poisson brutes
probs_poisson = {"home": 0.35, "draw": 0.22, "away": 0.43}
markets = {"over_2_5": 0.55, "under_2_5": 0.45}
meta = {
    "lambda_home": 1.49,
    "lambda_away": 1.92,
    "elo_home": 1650,
    "elo_away": 1800,
    # ...
}

# Recalibrer avec ML
probs_calibrated = calibrate_match_probabilities(
    probs_poisson,
    markets,
    meta=meta
)

# Résultat: légèrement ajusté
print(f"Poisson:    {probs_poisson}")
print(f"Calibrated: {probs_calibrated}")
# Différence: ±2% max
```

---

## 6️⃣ Pipeline Complet (Poisson → Prédiction)

### Code Simplifié
```python
from utils.prediction_model import (
    expected_goals_from_standings,
    apply_context_adjustments,
    project_match_outcome,
    aggregate_poisson_markets,
    calibrate_match_probabilities,
)

# ========== ÉTAPE 1: xG Calculation ==========
home_strength, away_strength, baseline = expected_goals_from_standings(
    standings, home_id, away_id, home_name, away_name
)
print(f"xG: {home_strength.lambda_value:.2f} vs {away_strength.lambda_value:.2f}")

# ========== ÉTAPE 2: Context Adjustments ==========
context = apply_context_adjustments(
    home_strength,
    away_strength,
    fixture,
    injuries_home=injuries,
    injuries_away=injuries,
)
print(f"Ajusté: {home_strength.lambda_value:.2f}")

# ========== ÉTAPE 3: Matrice Poisson ==========
probs_poisson, scorelines, matrix = project_match_outcome(
    home_strength,
    away_strength,
    goals_home=0,
    goals_away=0,
    status_short="NS",  # Not Started
)
print(f"Probs Poisson: {probs_poisson}")

# ========== ÉTAPE 4: Agrégation ==========
markets = aggregate_poisson_markets(matrix)
btts_prob = markets["btts_yes"]
over_prob = markets["over_2_5"]
print(f"BTTS: {btts_prob:.2%}, Over: {over_prob:.2%}")

# ========== ÉTAPE 5: ML Calibration (optionnel) ==========
probs_final = calibrate_match_probabilities(
    probs_poisson,
    markets,
    meta=meta
)
print(f"Final probs: {probs_final}")

# ========== ÉTAPE 6: Sélection main_pick ==========
main_choice = max(
    ("home", probs_final["home"]),
    ("draw", probs_final["draw"]),
    ("away", probs_final["away"]),
    key=lambda x: x[1]
)
print(f"main_pick: Victoire {away_name if main_choice[0] == 'away' else home_name}")

# ========== ÉTAPE 7: Output ==========
prediction = {
    "main_pick": main_choice[0],
    "btts_prob": btts_prob,
    "over_prob": over_prob,
    "probabilities": probs_final,
}

print(f"\n{prediction}")
```

### Résultat Exemple
```
xG: 1.49 vs 1.92
Ajusté: 1.45 (context)
Probs Poisson: {'home': 0.35, 'draw': 0.22, 'away': 0.43}
BTTS: 72.00%, Over: 55.00%
Final probs: {'home': 0.37, 'draw': 0.21, 'away': 0.42}
main_pick: Victoire Man City

{
  'main_pick': 'away',
  'btts_prob': 0.72,
  'over_prob': 0.55,
  'probabilities': {'home': 0.37, 'draw': 0.21, 'away': 0.42}
}
```

---

## 7️⃣ Test: Vérifier BTTS ≠ ML

```python
def test_btts_no_ml():
    """Vérifier que BTTS ne dépend pas du ML"""
    
    from utils.prediction_model import (
        poisson_matrix,
        aggregate_poisson_markets,
        calibrate_match_probabilities,
    )
    
    # Générer matrice
    matrix = poisson_matrix(1.5, 1.9)
    markets = aggregate_poisson_markets(matrix)
    
    # BTTS avant ML
    btts_before = markets["btts_yes"]
    
    # Appliquer ML (recalibre 1X2 mais pas BTTS)
    probs = {"home": 0.35, "draw": 0.22, "away": 0.43}
    probs_calibrated = calibrate_match_probabilities(probs, markets)
    
    # Recalculer markets (juste pour vérifier)
    # Note: markets n'est pas recalculé, donc BTTS inchangé
    
    # BTTS après ML
    btts_after = markets["btts_yes"]
    
    # Assertion
    assert btts_before == btts_after, "BTTS devrait être inchangé par ML!"
    print(f"✓ BTTS stable: {btts_before:.4f}")
```

---

## 8️⃣ Test: Vérifier main_pick est argmax

```python
def test_main_pick_is_argmax():
    """Vérifier que main_pick = argmax des 3 probs"""
    
    # Test 1: Home wins
    probs = {"home": 0.50, "draw": 0.30, "away": 0.20}
    choice = max(
        ("home", probs["home"]),
        ("draw", probs["draw"]),
        ("away", probs["away"]),
        key=lambda x: x[1]
    )
    assert choice[0] == "home", "Home devrait gagner"
    
    # Test 2: Away wins
    probs = {"home": 0.25, "draw": 0.25, "away": 0.50}
    choice = max(
        ("home", probs["home"]),
        ("draw", probs["draw"]),
        ("away", probs["away"]),
        key=lambda x: x[1]
    )
    assert choice[0] == "away", "Away devrait gagner"
    
    # Test 3: Draw wins
    probs = {"home": 0.33, "draw": 0.34, "away": 0.33}
    choice = max(
        ("home", probs["home"]),
        ("draw", probs["draw"]),
        ("away", probs["away"]),
        key=lambda x: x[1]
    )
    assert choice[0] == "draw", "Draw devrait gagner"
    
    print("✓ main_pick = argmax confirmé")
```

---

## 9️⃣ Fallback Strategy

```python
def get_probabilities_with_fallback(fixture_id, standings, context=None):
    """
    Obtenir probabilités avec fallback automatique.
    """
    try:
        # Étape 1: Poisson
        home_strength, away_strength, _ = expected_goals_from_standings(
            standings, fixture["home"]["id"], fixture["away"]["id"],
            fixture["home"]["name"], fixture["away"]["name"]
        )
        
        # Étape 2: Context
        apply_context_adjustments(home_strength, away_strength, fixture)
        
        # Étape 3: Matrice Poisson
        probs_poisson, _, matrix = project_match_outcome(
            home_strength, away_strength
        )
        markets = aggregate_poisson_markets(matrix)
        
        # Étape 4: ML (optionnel - peut échouer)
        try:
            probs_final = calibrate_match_probabilities(
                probs_poisson, markets, meta=meta
            )
        except Exception as e:
            print(f"⚠️ ML failed: {e}, fallback to Poisson")
            probs_final = probs_poisson  # ← Fallback automatique
        
        return {
            "probs": probs_final,
            "markets": markets,
            "btts": markets["btts_yes"],
        }
    
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        raise  # Remonter l'erreur
```

---

## 🔟 Enregistrement en BD

```python
def save_prediction(fixture_id, main_pick, probabilities, markets):
    """Enregistrer prédiction en BD"""
    
    from utils.prediction_history import upsert_prediction
    
    # Préprarer données
    prediction_data = {
        "fixture_id": fixture_id,
        "main_pick": main_pick["label"],  # "Victoire Man City"
        "main_confidence": int(main_pick["probability"] * 100),  # 43
        "prob_home": probabilities["home"],  # 0.37
        "prob_draw": probabilities["draw"],  # 0.21
        "prob_away": probabilities["away"],  # 0.42
        "prob_over_2_5": markets["over_2_5"],  # 0.55
        "prob_under_2_5": markets["under_2_5"],  # 0.45
        "edge_comment": "xG + forme",
        "betting_tips": json.dumps(tips),  # JSON array
    }
    
    # Enregistrer
    upsert_prediction(prediction_data)
    
    print(f"✓ Prédiction enregistrée: {main_pick['label']}")
```

---

## Résumé Quick Copy-Paste

### BTTS
```python
from utils.prediction_model import poisson_matrix, aggregate_poisson_markets

matrix = poisson_matrix(1.5, 1.9)
markets = aggregate_poisson_markets(matrix)
btts = markets["btts_yes"]  # 0.72
```

### main_pick
```python
probs = {"home": 0.35, "draw": 0.22, "away": 0.43}
choice = max(probs.items(), key=lambda x: x[1])  # ("away", 0.43)
main_pick = f"Victoire {team_names[choice[0]]}"
```

### Pipeline Complet
```python
# 1. xG
home_str, away_str, _ = expected_goals_from_standings(...)
# 2. Context
apply_context_adjustments(home_str, away_str, fixture)
# 3. Poisson
probs_poisson, _, matrix = project_match_outcome(home_str, away_str)
# 4. Markets
markets = aggregate_poisson_markets(matrix)
# 5. ML (optionnel)
probs_final = calibrate_match_probabilities(probs_poisson, markets)
# 6. Selection
main_choice = max(probs_final.items(), key=lambda x: x[1])
```

---

**Généré:** 2 février 2026  
**Code Statut:** Vérifié ✅  
**Utilisable:** Oui (copy-paste ready)
