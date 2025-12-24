from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from .api_calls import get_fixture_events

EVENT_ICONS = {
    "goal": "⚽",
    "card-yellow": "🟨",
    "card-second yellow": "🟨🟥",
    "card-red": "🟥",
    "subst": "🔁",
    "penalty": "⚽ (pen.)",
    "missed penalty": "❌ (pen.)",
    "shot-woodwork": "🥅",
    "goal-own": "🚨",
}

WOODWORK_KEYWORDS = ("woodwork", "post", "crossbar", "barre", "poteau")
OWN_GOAL_KEYWORDS = ("own goal", "contre son camp", "csc", "auto goal", "autogoal")


def _contains_keyword(text: Optional[str], keywords: tuple[str, ...]) -> bool:
    if not text:
        return False
    normalized = text.lower()
    return any(keyword in normalized for keyword in keywords)


def _is_woodwork(*texts: Optional[str]) -> bool:
    return any(_contains_keyword(text, WOODWORK_KEYWORDS) for text in texts)


def _is_own_goal(*texts: Optional[str]) -> bool:
    return any(_contains_keyword(text, OWN_GOAL_KEYWORDS) for text in texts)


def _icon_for_event(event_type: str, detail: str, comments: Optional[str] = None) -> str:
    normalized_detail = detail.lower() if detail else ""
    if event_type.lower() == "goal" and _is_own_goal(detail, comments):
        return EVENT_ICONS.get("goal-own", "🚨")
    if event_type.lower() in {"shot", "goal"} and _is_woodwork(detail, comments):
        return EVENT_ICONS.get("shot-woodwork", "🥅")
    key = f"{event_type.lower()}-{normalized_detail}" if detail else event_type.lower()
    if key in EVENT_ICONS:
        return EVENT_ICONS[key]
    if event_type.lower() == "goal":
        return EVENT_ICONS["goal"]
    if event_type.lower() == "card":
        if "yellow" in detail.lower():
            return EVENT_ICONS.get("card-yellow", "🟨")
        if "red" in detail.lower():
            return EVENT_ICONS.get("card-red", "🟥")
    if event_type.lower() == "subst":
        return EVENT_ICONS.get("subst", "🔁")
    return "•"


@st.cache_data(ttl=30, show_spinner=False)
def load_fixture_events(fixture_id: int) -> List[Dict[str, Any]]:
    if not fixture_id:
        return []
    try:
        payload = get_fixture_events(fixture_id) or []
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    events: List[Dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        event_type = entry.get("type") or ""
        detail = entry.get("detail") or ""
        comments = entry.get("comments") or entry.get("comment")
        time_info = entry.get("time") or {}
        elapsed = time_info.get("elapsed")
        extra = time_info.get("extra")
        minute = f"{elapsed}'" if elapsed is not None else ""
        if extra:
            minute = f"{minute}+{extra}"
        player = entry.get("player", {}).get("name") or ""
        team = entry.get("team", {}).get("name") or ""
        assist = entry.get("assist", {}).get("name")
        score = entry.get("score")
        icon = _icon_for_event(event_type, detail, comments)
        events.append(
            {
                "minute": minute,
                "player": player or assist or "Inconnu",
                "team": team,
                "detail": detail,
                "comments": comments,
                "type": event_type,
                "assist": assist,
                "icon": icon,
                "score": score,
            }
        )
    return events


def format_event_line(event: Dict[str, Any]) -> str:
    raw_detail = event.get("detail")
    raw_comments = event.get("comments")
    detail = ""
    if raw_detail or raw_comments:
        if _is_own_goal(raw_detail, raw_comments):
            detail = " (But contre son camp)"
        elif _is_woodwork(raw_detail, raw_comments):
            detail = " (Poteau)"
        else:
            extra = raw_detail or raw_comments or ""
            if raw_detail and raw_comments and raw_comments.lower() not in raw_detail.lower():
                extra = f"{raw_detail} - {raw_comments}"
            detail = f" ({extra})"
    team = event.get("team")
    team_label = f" - {team}" if team else ""
    score = event.get("score")
    score_label = f" _{score}_" if score else ""
    player = event.get("player") or "Inconnu"
    minute = event.get("minute") or ""
    icon = event.get("icon", "•")
    return f"{icon} {minute} **{player}**{team_label}{detail}{score_label}"


__all__ = ["load_fixture_events", "format_event_line"]
