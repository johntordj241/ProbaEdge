from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional

from .profile import DEFAULT_BANKROLL, get_bankroll_settings, save_bankroll_settings


def calculer_roi(gains: float, mises: float) -> float:
    if mises == 0:
        return 0.0
    return (gains - mises) / mises


def calculer_confiance(nb_paris_gagnes: int, nb_paris_totaux: int) -> float:
    if nb_paris_totaux == 0:
        return 0.0
    return nb_paris_gagnes / nb_paris_totaux


@dataclass
class BankrollSettings:
    amount: float
    strategy: str
    flat_stake: float
    percent: float
    kelly_fraction: float
    default_odds: float
    min_stake: float
    max_stake: float
    profile_id: Optional[str] = None
    profile_name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "BankrollSettings":
        source = DEFAULT_BANKROLL.copy()
        if isinstance(data, dict):
            source.update({key: data.get(key, source[key]) for key in source})
        return cls(
            amount=float(max(0.0, source["amount"])),
            strategy=str(source.get("strategy", "percent")),
            flat_stake=float(max(0.0, source.get("flat_stake", 0.0))),
            percent=float(max(0.0, source.get("percent", 0.0))),
            kelly_fraction=float(min(1.0, max(0.0, source.get("kelly_fraction", 0.0)))),
            default_odds=float(max(1.01, source.get("default_odds", 1.01))),
            min_stake=float(max(0.0, source.get("min_stake", 0.0))),
            max_stake=float(max(0.0, source.get("max_stake", 0.0))),
            profile_id=str(source.get("profile_id") or source.get("id") or "") or None,
            profile_name=str(
                source.get("profile_name") or source.get("name") or ""
            ).strip()
            or None,
        )


def _clamp_stake(stake: float, settings: BankrollSettings) -> float:
    if stake <= 0:
        return 0.0
    stake = min(stake, settings.amount)
    if settings.max_stake > 0:
        stake = min(stake, settings.max_stake)
    if settings.min_stake > 0:
        stake = max(stake, settings.min_stake)
    return stake


def suggest_stake(
    probability: float, odds: Optional[float], settings: BankrollSettings
) -> Dict[str, float]:
    prob = max(0.0, min(1.0, float(probability or 0.0)))
    if odds is None or odds <= 1.0:
        odds = settings.default_odds
    odds = max(1.01, float(odds))

    if prob == 0.0:
        return {
            "stake": 0.0,
            "edge": -1.0,
            "expected_profit": 0.0,
            "odds": odds,
            "status": "zero_probability",
        }

    edge = (prob * odds) - 1.0
    if edge <= 0:
        return {
            "stake": 0.0,
            "edge": edge,
            "expected_profit": 0.0,
            "odds": odds,
            "status": "negative_edge",
        }

    strategy = settings.strategy or "percent"
    stake = 0.0
    if strategy == "flat":
        stake = settings.flat_stake
    elif strategy == "percent":
        stake = settings.amount * (settings.percent / 100.0)
    elif strategy == "kelly":
        b = odds - 1.0
        if b > 0:
            fraction = ((odds * prob) - 1.0) / b
            fraction = max(0.0, fraction)
            stake = settings.amount * fraction * settings.kelly_fraction
        else:
            stake = 0.0
    else:
        stake = settings.amount * (settings.percent / 100.0)

    # Respect explicit max_stake if provided, else apply default 3% bankroll cap
    if settings.max_stake > 0:
        stake = min(stake, settings.max_stake)
    else:
        max_bankroll_stake = settings.amount * 0.03
        stake = min(stake, max_bankroll_stake)

    stake = _clamp_stake(stake, settings)
    if stake <= 0:
        return {
            "stake": 0.0,
            "edge": edge,
            "expected_profit": 0.0,
            "odds": odds,
            "status": "no_bankroll",
        }

    status = "ok"
    if settings.max_stake > 0 and math.isclose(stake, settings.max_stake, rel_tol=1e-6):
        status = "capped_max"
    elif math.isclose(stake, settings.amount, rel_tol=1e-6):
        status = "all_bankroll"
    elif settings.min_stake > 0 and math.isclose(
        stake, settings.min_stake, rel_tol=1e-6
    ):
        status = "min_enforced"

    expected_profit = stake * edge
    return {
        "stake": round(stake, 2),
        "edge": edge,
        "expected_profit": round(expected_profit, 2),
        "odds": odds,
        "status": status,
    }


def adjust_bankroll(delta: float, profile_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply a delta (positive or negative) to the persisted bankroll amount.
    Useful to debit the stake at bet placement and credit payouts once settled.
    """
    try:
        current = dict(get_bankroll_settings(profile_id))
    except Exception:
        current = DEFAULT_BANKROLL.copy()
    try:
        amount = float(current.get("amount", DEFAULT_BANKROLL["amount"]))
    except (TypeError, ValueError):
        amount = DEFAULT_BANKROLL["amount"]
    new_amount = max(0.0, amount + float(delta or 0.0))
    current["amount"] = round(new_amount, 2)
    target_profile_id = profile_id or current.get("profile_id")
    save_bankroll_settings(current, profile_id=target_profile_id)
    return current


__all__ = [
    "calculer_roi",
    "calculer_confiance",
    "BankrollSettings",
    "suggest_stake",
    "adjust_bankroll",
]
