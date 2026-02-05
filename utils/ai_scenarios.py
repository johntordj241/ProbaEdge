from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping, Tuple

ScenarioConfig = Dict[str, Any]

SCENARIO_LIBRARY: Dict[str, ScenarioConfig] = {
    "red_card_home": {
        "label": "Carton rouge (domicile)",
        "description": "L'équipe à domicile joue à 10 et perd en intensité offensive.",
        "instruction": "Imagine que l'équipe locale vient de recevoir un carton rouge. Ajuste ton analyse en conséquence.",
        "context_flag": "carton rouge domicile",
        "probability_factors": {"home": 0.65, "draw": 1.1, "away": 1.25},
    },
    "heavy_rain": {
        "label": "Conditions météo difficiles",
        "description": "Pluie forte / pelouse lourde : le rythme baisse et les buts se raréfient.",
        "instruction": "Suppose que la météo devient très pluvieuse avec une pelouse lourde limitant les occasions.",
        "context_flag": "météo extrême",
        "probability_factors": {"home": 0.95, "draw": 1.15, "away": 0.95},
    },
    "early_goal_home": {
        "label": "But rapide (domicile)",
        "description": "L'équipe locale mène d'un but après 10 minutes.",
        "instruction": "Considère que l'équipe locale ouvre le score très tôt et analyse les conséquences.",
        "context_flag": "but rapide domicile",
        "probability_factors": {"home": 1.2, "draw": 0.9, "away": 0.85},
    },
    "early_goal_second_half": {
        "label": "But express (2e mi-temps)",
        "description": "Un but tombe des la reprise et accelere fortement le rythme.",
        "instruction": "Imagine qu'une equipe marque dans les cinq premieres minutes de la seconde periode et explique comment cela impacte les paris.",
        "context_flag": "but rapide seconde mi-temps",
        "probability_factors": {"home": 1.05, "draw": 0.88, "away": 1.05},
    },
}

DEFAULT_AI_SCENARIOS: Tuple[str, ...] = ("red_card_home", "heavy_rain", "early_goal_home", "early_goal_second_half")


def available_scenarios() -> Dict[str, ScenarioConfig]:
    return SCENARIO_LIBRARY


def scenario_config(key: str) -> ScenarioConfig:
    if key not in SCENARIO_LIBRARY:
        raise KeyError(f"Scenario inconnu : {key}")
    return SCENARIO_LIBRARY[key]


def build_scenario_payload(base_payload: Mapping[str, Any], scenario_key: str) -> Dict[str, Any]:
    config = scenario_config(scenario_key)
    payload = deepcopy(base_payload)
    scenario_label = config["label"]
    scenario_section = payload.setdefault("scenario", {})
    scenario_section.update(
        {
            "key": scenario_key,
            "label": scenario_label,
            "description": config.get("description", ""),
        }
    )
    context_block = payload.setdefault("context", {})
    flags = context_block.setdefault("scenario_flags", [])
    if isinstance(flags, list):
        flags.append(config.get("context_flag", scenario_label))
    else:
        context_block["scenario_flags"] = [config.get("context_flag", scenario_label)]
    return payload


def scenario_instruction(base_payload: Mapping[str, Any], scenario_key: str) -> str:
    config = scenario_config(scenario_key)
    teams = base_payload.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})
    home_name = home.get("name") or "l'équipe locale"
    away_name = away.get("name") or "l'équipe visiteuse"
    template = config.get("instruction") or config.get("description") or "Adapte ton analyse."
    return template.replace("{home}", str(home_name)).replace("{away}", str(away_name))


def scenario_probability_factors(scenario_key: str) -> Dict[str, float]:
    config = scenario_config(scenario_key)
    return config.get("probability_factors", {})


def scenario_options(keys: Iterable[str] | None = None) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    for key, config in SCENARIO_LIBRARY.items():
        if keys and key not in keys:
            continue
        entries.append((key, config["label"]))
    return entries
