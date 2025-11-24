from __future__ import annotations

import csv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import unicodedata
import re
from typing import Any, Dict, Iterable, List, Optional, Union

import numpy as np
import pandas as pd

from .api_calls import get_fixture_details
from .cache import is_offline_mode
from .bankroll import adjust_bankroll

PARIS_TZ = ZoneInfo("Europe/Paris")

PREDICTION_HISTORY_PATH = Path('data/prediction_history.csv')
PREDICTION_DATASET_PATH = Path('data/prediction_dataset.csv')
HEADER = [
    'timestamp','fixture_date','fixture_id','league_id','season','home_team','away_team',
    'prob_home','prob_draw','prob_away','prob_over_2_5','prob_under_2_5',
    'main_pick','main_confidence','edge_comment','top_score','total_pick',
    'bet_selection','bet_bookmaker','bet_odd','bet_stake','bet_timestamp','bet_notes','bet_result','bet_return',
    'status_snapshot','result_status','result_score','result_winner','updated_at',
    'feature_home_draw_diff','feature_home_away_diff','feature_over_under_diff','feature_max_prob',
    'feature_main_confidence_norm','feature_total_pick_over',
    'feature_lambda_home','feature_lambda_away','elo_home','elo_away','delta_elo','pressure_score','intensity_score'
]
FLOAT_COLUMNS = {
    'prob_home','prob_draw','prob_away','prob_over_2_5','prob_under_2_5','bet_odd','bet_stake','bet_return',
    'feature_home_draw_diff','feature_home_away_diff','feature_over_under_diff','feature_max_prob','feature_main_confidence_norm',
    'feature_lambda_home','feature_lambda_away','elo_home','elo_away','delta_elo','pressure_score','intensity_score'
}
FINISHED_STATUS = {"FT", "AET", "PEN"}


def _normalize_fixture_id(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    try:
        return str(int(float(token)))
    except (TypeError, ValueError):
        return token

SAMPLE_ROWS: List[Dict[str, Any]] = [
    {
        'timestamp': '2025-09-28T07:50:00+00:00',
        'fixture_date': '2025-09-28T12:30:00+00:00',
        'fixture_id': '900001',
        'league_id': '3',
        'season': '2025',
        'home_team': 'Liverpool',
        'away_team': 'West Ham',
        'prob_home': 0.62,
        'prob_draw': 0.22,
        'prob_away': 0.16,
        'prob_over_2_5': 0.58,
        'prob_under_2_5': 0.42,
        'main_pick': 'Victoire Liverpool',
        'main_confidence': 82,
        'edge_comment': 'xG + forme domicile',
        'top_score': '2-1',
        'total_pick': 'Over 2.5 buts',
        'bet_selection': '',
        'bet_bookmaker': '',
        'bet_odd': '',
        'bet_stake': '',
        'bet_timestamp': '',
        'bet_notes': '',
        'bet_result': '',
        'bet_return': '',
        'status_snapshot': 'NS',
        'result_status': 'FT',
        'result_score': '2-1',
        'result_winner': 'home',
        'updated_at': '2025-09-28T18:00:00'
    },
    {
        'timestamp': '2025-09-28T08:45:00+00:00',
        'fixture_date': '2025-09-28T15:00:00+00:00',
        'fixture_id': '900002',
        'league_id': '61',
        'season': '2025',
        'home_team': 'Lille',
        'away_team': 'Nice',
        'prob_home': 0.44,
        'prob_draw': 0.28,
        'prob_away': 0.28,
        'prob_over_2_5': 0.52,
        'prob_under_2_5': 0.48,
        'main_pick': 'Double chance 1X (Lille)',
        'main_confidence': 68,
        'edge_comment': 'Valeur sur la double chance',
        'top_score': '1-1',
        'total_pick': 'BTTS : Non',
        'bet_selection': '',
        'bet_bookmaker': '',
        'bet_odd': '',
        'bet_stake': '',
        'bet_timestamp': '',
        'bet_notes': '',
        'bet_result': '',
        'bet_return': '',
        'status_snapshot': 'NS',
        'result_status': 'FT',
        'result_score': '1-1',
        'result_winner': 'draw',
        'updated_at': '2025-09-28T21:15:00'
    },
    {
        'timestamp': '2025-09-29T09:20:00+00:00',
        'fixture_date': '2025-09-29T19:45:00+00:00',
        'fixture_id': '900003',
        'league_id': '39',
        'season': '2025',
        'home_team': 'Brentford',
        'away_team': 'Arsenal',
        'prob_home': 0.18,
        'prob_draw': 0.24,
        'prob_away': 0.58,
        'prob_over_2_5': 0.61,
        'prob_under_2_5': 0.39,
        'main_pick': 'Victoire Arsenal',
        'main_confidence': 79,
        'edge_comment': 'Arsenal domine offensivement',
        'top_score': '1-2',
        'total_pick': 'Over 2.5 buts',
        'bet_selection': '',
        'bet_bookmaker': '',
        'bet_odd': '',
        'bet_stake': '',
        'bet_timestamp': '',
        'bet_notes': '',
        'bet_result': '',
        'bet_return': '',
        'status_snapshot': 'NS',
        'result_status': 'FT',
        'result_score': '0-2',
        'result_winner': 'away',
        'updated_at': '2025-09-29T20:45:00'
    },
    {
        'timestamp': '2025-09-29T10:50:00+00:00',
        'fixture_date': '2025-09-29T20:00:00+00:00',
        'fixture_id': '900004',
        'league_id': '4',
        'season': '2025',
        'home_team': 'Celta Vigo',
        'away_team': 'Sevilla',
        'prob_home': 0.36,
        'prob_draw': 0.32,
        'prob_away': 0.32,
        'prob_over_2_5': 0.67,
        'prob_under_2_5': 0.33,
        'main_pick': 'Over 2.5 buts',
        'main_confidence': 65,
        'edge_comment': 'Deux defenses permissives',
        'top_score': '2-2',
        'total_pick': 'Over 2.5 buts',
        'bet_selection': '',
        'bet_bookmaker': '',
        'bet_odd': '',
        'bet_stake': '',
        'bet_timestamp': '',
        'bet_notes': '',
        'bet_result': '',
        'bet_return': '',
        'status_snapshot': 'NS',
        'result_status': 'FT',
        'result_score': '1-2',
        'result_winner': 'away',
        'updated_at': '2025-09-29T23:00:00'
    },
    {
        'timestamp': '2025-09-30T07:15:00+00:00',
        'fixture_date': '2025-09-30T18:00:00+00:00',
        'fixture_id': '900005',
        'league_id': '2',
        'season': '2025',
        'home_team': 'Juventus',
        'away_team': 'Atalanta',
        'prob_home': 0.48,
        'prob_draw': 0.27,
        'prob_away': 0.25,
        'prob_over_2_5': 0.45,
        'prob_under_2_5': 0.55,
        'main_pick': 'Victoire Juventus',
        'main_confidence': 70,
        'edge_comment': 'Edge leger en 1X2',
        'top_score': '2-1',
        'total_pick': 'Under 2.5 buts',
        'bet_selection': '',
        'bet_bookmaker': '',
        'bet_odd': '',
        'bet_stake': '',
        'bet_timestamp': '',
        'bet_notes': '',
        'bet_result': '',
        'bet_return': '',
        'status_snapshot': 'NS',
        'result_status': 'FT',
        'result_score': '1-0',
        'result_winner': 'home',
        'updated_at': '2025-09-30T19:30:00'
    }
]


def _ensure_file() -> None:
    PREDICTION_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PREDICTION_HISTORY_PATH.exists():
        with PREDICTION_HISTORY_PATH.open('w', encoding='utf-8', newline='') as handle:
            csv.DictWriter(handle, fieldnames=HEADER).writeheader()


def load_prediction_history(path: str = 'data/prediction_history.csv') -> pd.DataFrame:
    _ensure_file()
    return pd.read_csv(path)


def _default_timestamp() -> str:
    return datetime.now(PARIS_TZ).isoformat()


def _total_goals_from_score(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {'nan', 'na'}:
        return None
    parts = re.split(r'[--]', text)
    if len(parts) < 2:
        return None
    try:
        home = int(parts[0].strip())
        away = int(parts[1].strip())
    except (TypeError, ValueError):
        return None
    return home + away


def _strip_accents(text: Any) -> str:
    normalized = unicodedata.normalize('NFKD', str(text or ''))
    return ''.join(ch for ch in normalized if ord(ch) < 128)


def _normalize_label(text: Any) -> str:
    ascii_text = _strip_accents(text).lower()
    return re.sub(r'\s+', ' ', ascii_text).strip()


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == '' or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        value = value.replace(',', '.').strip()
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_score_tokens(value: Any) -> tuple[Optional[int], Optional[int]]:
    if value is None:
        return (None, None)
    match = re.match(r'\s*(\d+)\s*[-:]\s*(\d+)\s*$', str(value).strip())
    if not match:
        return (None, None)
    try:
        return int(match.group(1)), int(match.group(2))
    except (TypeError, ValueError):
        return (None, None)


def _line_outcome(goals: int, threshold: float, direction: str) -> str:
    epsilon = 1e-9
    threshold = float(threshold)
    is_integer_line = abs(threshold - round(threshold)) < epsilon
    if direction == 'over':
        if goals - threshold > epsilon:
            return 'win'
        if is_integer_line and abs(goals - threshold) <= epsilon:
            return 'void'
        return 'loss'
    if direction == 'under':
        if threshold - goals > epsilon:
            return 'win'
        if is_integer_line and abs(goals - threshold) <= epsilon:
            return 'void'
        return 'loss'
    return 'void'


def _extract_threshold(label: str, keyword: str) -> Optional[float]:
    match = re.search(rf'{keyword}\s+([0-9]+(?:[.,][0-9])?)', label)
    if not match:
        return None
    try:
        return float(match.group(1).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def _settle_bet_outcome(
    selection: str,
    stake: Optional[float],
    odd: Optional[float],
    home_name: Optional[str],
    away_name: Optional[str],
    goals_home: Optional[int],
    goals_away: Optional[int],
) -> tuple[Optional[str], Optional[float]]:
    if not selection or stake is None or stake <= 0:
        return (None, None)
    if goals_home is None or goals_away is None:
        return (None, None)

    normalized = _normalize_label(selection)
    if not normalized:
        return (None, None)
    normalized = normalized.replace('plus de', 'over').replace('moins de', 'under')
    home_norm = _normalize_label(home_name) if home_name else ''
    away_norm = _normalize_label(away_name) if away_name else ''
    home_win = goals_home > goals_away
    away_win = goals_away > goals_home
    is_draw = goals_home == goals_away
    total_goals = goals_home + goals_away
    odd_value = odd if (odd is not None and odd > 0) else 1.0

    def payout(result: str) -> float:
        if result == 'win':
            return round(stake * odd_value, 2)
        if result == 'void':
            return round(stake, 2)
        if result == 'loss':
            return 0.0
        return 0.0

    if 'double chance' in normalized:
        if '1x' in normalized:
            result = 'win' if home_win or is_draw else 'loss'
            return result, payout(result)
        if 'x2' in normalized:
            result = 'win' if away_win or is_draw else 'loss'
            return result, payout(result)
        if '12' in normalized:
            result = 'win' if not is_draw else 'loss'
            return result, payout(result)

    if 'draw no bet' in normalized or 'rembourse si nul' in normalized:
        if is_draw:
            return 'void', payout('void')
        target = None
        if home_norm and home_norm in normalized:
            target = 'home'
        elif away_norm and away_norm in normalized:
            target = 'away'
        if target == 'home':
            result = 'win' if home_win else 'loss'
            return result, payout(result)
        if target == 'away':
            result = 'win' if away_win else 'loss'
            return result, payout(result)

    if 'match nul' in normalized or normalized in {'nul', 'draw'}:
        result = 'win' if is_draw else 'loss'
        return result, payout(result)

    if 'btts' in normalized or 'deux equipes marquent' in normalized:
        both_score = goals_home > 0 and goals_away > 0
        if 'non' in normalized and ('btts' in normalized or 'marquent' in normalized):
            result = 'win' if not both_score else 'loss'
            return result, payout(result)
        threshold = _extract_threshold(normalized, 'over')
        if threshold is not None and ('+' in normalized or 'et' in normalized):
            line_result = _line_outcome(total_goals, threshold, 'over')
            if both_score and line_result == 'win':
                return 'win', payout('win')
            if line_result == 'void' and both_score:
                return 'void', payout('void')
            return 'loss', payout('loss')
        result = 'win' if both_score else 'loss'
        return result, payout(result)

    over_threshold = _extract_threshold(normalized, 'over')
    under_threshold = _extract_threshold(normalized, 'under')
    if over_threshold is not None:
        scope_goals = total_goals
        if home_norm and home_norm in normalized:
            scope_goals = goals_home
        elif away_norm and away_norm in normalized:
            scope_goals = goals_away
        result = _line_outcome(scope_goals, over_threshold, 'over')
        return result, payout(result)
    if under_threshold is not None:
        scope_goals = total_goals
        if home_norm and home_norm in normalized:
            scope_goals = goals_home
        elif away_norm and away_norm in normalized:
            scope_goals = goals_away
        result = _line_outcome(scope_goals, under_threshold, 'under')
        return result, payout(result)

    victory_keywords = ('victoire', 'vainqueur', 'winner', 'gagnant', 'win ')
    if any(keyword in normalized for keyword in victory_keywords):
        if home_norm and home_norm in normalized:
            result = 'win' if home_win else 'loss'
            return result, payout(result)
        if away_norm and away_norm in normalized:
            result = 'win' if away_win else 'loss'
            return result, payout(result)

    if home_norm and home_norm in normalized:
        result = 'win' if home_win else 'loss'
        return result, payout(result)
    if away_norm and away_norm in normalized:
        result = 'win' if away_win else 'loss'
        return result, payout(result)

    return (None, None)


def _normalize_timestamp_value(value: Any, *, allow_blank: bool = False) -> str:
    if value in {None, '', float('nan')}:
        return '' if allow_blank else _default_timestamp()
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        try:
            parsed = pd.to_datetime(value, errors='coerce')
            if pd.isna(parsed):
                return '' if allow_blank else _default_timestamp()
            parsed = parsed.to_pydatetime()
        except Exception:
            return '' if allow_blank else _default_timestamp()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        parsed = parsed.astimezone(PARIS_TZ)
    except Exception:
        pass
    return parsed.isoformat()


def upsert_prediction(entry: Dict[str, Any]) -> None:
    if is_offline_mode():
        return
    _ensure_file()
    payload = {key: entry.get(key, '') for key in HEADER}
    payload['timestamp'] = _normalize_timestamp_value(payload.get('timestamp'))
    payload['fixture_date'] = _normalize_timestamp_value(payload.get('fixture_date'), allow_blank=True)
    fixture_id = _normalize_fixture_id(payload.get('fixture_id'))
    payload['fixture_id'] = fixture_id
    status_snapshot = str(payload.get('status_snapshot', '') or '').strip()
    if not fixture_id:
        with PREDICTION_HISTORY_PATH.open('a', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER)
            writer.writerow(payload)
        return

    df = pd.read_csv(PREDICTION_HISTORY_PATH)
    if df.empty or 'fixture_id' not in df.columns:
        with PREDICTION_HISTORY_PATH.open('a', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER)
            writer.writerow(payload)
        return

    fixture_series = df['fixture_id'].astype(str).str.strip().apply(_normalize_fixture_id)
    status_series = df.get('status_snapshot', pd.Series([], dtype=str)).fillna('').astype(str).str.strip()
    mask = (fixture_series == fixture_id) & (status_series == status_snapshot)
    if not mask.any():
        with PREDICTION_HISTORY_PATH.open('a', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER)
            writer.writerow(payload)
        return

    idx = mask[mask].index[0]
    for key in HEADER:
        df.at[idx, key] = payload.get(key, '')
    df.to_csv(PREDICTION_HISTORY_PATH, index=False)


def append_prediction(entry: Dict[str, Any]) -> None:
    upsert_prediction(entry)


def _populate_fixture_dates(df: pd.DataFrame, mask: pd.Series) -> pd.Series:
    missing_ids = df.loc[mask, 'fixture_id'].dropna().astype(str).str.strip().unique()
    mapping: Dict[str, str] = {}
    for fixture in missing_ids[:75]:
        try:
            fixture_int = int(fixture)
        except (TypeError, ValueError):
            continue
        payload = get_fixture_details(fixture_int) or []
        entry = payload[0] if isinstance(payload, list) and payload else None
        if not isinstance(entry, dict):
            continue
        fixture_info = entry.get('fixture') or {}
        date_value = fixture_info.get('date')
        normalized = _normalize_timestamp_value(date_value, allow_blank=True)
        if normalized:
            mapping[_normalize_fixture_id(fixture_int)] = normalized
    if not mapping:
        return pd.Series(dtype=str)
    target_index = df.index[
        mask & df['fixture_id'].astype(str).str.strip().apply(_normalize_fixture_id).isin(mapping.keys())
    ]
    if target_index.empty:
        return pd.Series(dtype=str)
    values = df.loc[target_index, 'fixture_id'].astype(str).str.strip().apply(_normalize_fixture_id).map(mapping)
    return pd.Series(values.values, index=target_index)


def normalize_prediction_history(path: str = 'data/prediction_history.csv') -> int:
    _ensure_file()
    try:
        df = pd.read_csv(path)
    except Exception:
        return 0
    if df.empty:
        return 0

    for column in HEADER:
        if column not in df.columns:
            df[column] = pd.NA if column in FLOAT_COLUMNS else ''

    if 'fixture_date' not in df.columns:
        df['fixture_date'] = ''

    df['fixture_id'] = df.get('fixture_id', pd.Series(dtype=str)).apply(_normalize_fixture_id)
    df['status_snapshot'] = df.get('status_snapshot', pd.Series(dtype=str)).fillna('').astype(str).str.strip()
    df['timestamp'] = df.get('timestamp', pd.Series(dtype=str)).apply(_normalize_timestamp_value)
    df['fixture_date'] = df.get('fixture_date', pd.Series(dtype=str)).apply(
        lambda value: _normalize_timestamp_value(value, allow_blank=True)
    )
    for column in FLOAT_COLUMNS:
        df[column] = pd.to_numeric(df.get(column, pd.Series(dtype=float)), errors='coerce')
    total_pick_series = df.get('total_pick')
    if total_pick_series is None:
        total_pick_series = pd.Series(data='', index=df.index, dtype=object)
    else:
        total_pick_series = total_pick_series.fillna('').astype(str)
    engineered_map = {
        'feature_home_draw_diff': df['prob_home'] - df['prob_draw'],
        'feature_home_away_diff': df['prob_home'] - df['prob_away'],
        'feature_over_under_diff': df['prob_over_2_5'] - df['prob_under_2_5'],
        'feature_max_prob': df[['prob_home', 'prob_draw', 'prob_away']].max(axis=1),
        'feature_main_confidence_norm': pd.to_numeric(df.get('main_confidence', pd.Series(dtype=float)), errors='coerce') / 100.0,
        'feature_total_pick_over': total_pick_series.str.contains('over', case=False, na=False).astype(int),
    }
    for feature_name, series in engineered_map.items():
        df[feature_name] = series

    def _winner_token(row: pd.Series) -> str:
        value = str(row.get('result_winner', '') or '').strip().lower()
        if value in {'home', 'away', 'draw'}:
            return value
        home = str(row.get('home_team', '') or '').strip().lower()
        away = str(row.get('away_team', '') or '').strip().lower()
        if value == home:
            return 'home'
        if value == away:
            return 'away'
        if value in {'domicile', 'maison'}:
            return 'home'
        if value in {'extérieur', 'exterieur', 'visiteur'}:
            return 'away'
        if value in {'nul', 'draw'}:
            return 'draw'
        score = str(row.get('result_score', '') or '')
        if score and '-' in score:
            try:
                left, right = score.split('-', 1)
                left = int(left)
                right = int(right)
                if left > right:
                    return 'home'
                if right > left:
                    return 'away'
                return 'draw'
            except Exception:
                pass
        return value or ''

    df['result_winner'] = df.apply(_winner_token, axis=1)

    missing_mask = df['fixture_date'].isna() | (df['fixture_date'] == '')
    if missing_mask.any():
        filled = _populate_fixture_dates(df, missing_mask)
        if not filled.empty:
            df.loc[filled.index, 'fixture_date'] = filled

    def _normalize_text(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return unicodedata.normalize("NFC", value)

    for column in df.columns:
        if df[column].dtype == object:
            df[column] = df[column].apply(_normalize_text)

    df.sort_values('timestamp', inplace=True)
    before = len(df)
    df.drop_duplicates(subset=['fixture_id', 'status_snapshot'], keep='last', inplace=True)
    after = len(df)
    if 'result_winner' in df.columns:
        df.loc[~df['result_winner'].isin({'home', 'away', 'draw', ''}), 'result_winner'] = ''
    ordered_columns = [column for column in HEADER if column in df.columns]
    engineered_columns = [
        'feature_home_draw_diff',
        'feature_home_away_diff',
        'feature_over_under_diff',
        'feature_max_prob',
        'feature_main_confidence_norm',
        'feature_total_pick_over',
    ]
    for column in engineered_columns:
        if column in df.columns and column not in ordered_columns:
            ordered_columns.append(column)
    df = df[ordered_columns]
    df.to_csv(path, index=False)
    return before - after


def training_progress(target: int = 100) -> Dict[str, Any]:
    _ensure_file()
    try:
        df = pd.read_csv(PREDICTION_HISTORY_PATH)
    except Exception:
        return {"ready": 0, "target": target, "remaining": max(target, 0), "progress": 0.0}
    if df.empty:
        return {"ready": 0, "target": target, "remaining": max(target, 0), "progress": 0.0}

    df = df.copy()
    df["fixture_id_norm"] = df.get("fixture_id", pd.Series(dtype=str)).apply(_normalize_fixture_id)
    status_series = df.get("result_status", pd.Series(dtype=str)).fillna("").astype(str).str.upper()
    winner_series = df.get("result_winner", pd.Series(dtype=str)).fillna("").astype(str).str.lower()

    finished_mask = status_series.isin(FINISHED_STATUS)
    winner_mask = winner_series.isin({"home", "away", "draw"})

    ready_ids = set(df.loc[finished_mask & winner_mask, "fixture_id_norm"])
    ready_count = len(ready_ids)
    remaining = max(target - ready_count, 0)
    progress = min(ready_count / target, 1.0) if target > 0 else 1.0

    return {
        "ready": ready_count,
        "target": target,
        "remaining": remaining,
        "progress": progress,
    }


def update_outcome(
    fixture_id: Any,
    *,
    status: Optional[str],
    goals_home: Optional[int],
    goals_away: Optional[int],
    winner: Optional[str],
) -> bool:
    if is_offline_mode():
        return False
    _ensure_file()
    try:
        fixture_int = int(fixture_id)
    except (TypeError, ValueError):
        return False
    rows: List[Dict[str, Any]] = []
    updated = False
    bankroll_delta = 0.0
    with PREDICTION_HISTORY_PATH.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                current_id = int(row.get('fixture_id', 0))
            except (TypeError, ValueError):
                current_id = -1
            if current_id == fixture_int:
                if status:
                    row['result_status'] = status
                if goals_home is not None and goals_away is not None:
                    row['result_score'] = f"{goals_home}-{goals_away}"
                if winner:
                    row['result_winner'] = winner
                row['updated_at'] = pd.Timestamp.utcnow().isoformat()

                stake_value = _safe_float(row.get('bet_stake'))
                odd_value = _safe_float(row.get('bet_odd'))
                previous_return = _safe_float(row.get('bet_return')) or 0.0
                selection_label = row.get('bet_selection', '')
                home_name = row.get('home_team')
                away_name = row.get('away_team')
                score_home, score_away = _parse_score_tokens(row.get('result_score'))
                final_home = goals_home if goals_home is not None else score_home
                final_away = goals_away if goals_away is not None else score_away
                outcome, payout = _settle_bet_outcome(
                    selection_label,
                    stake_value,
                    odd_value,
                    home_name,
                    away_name,
                    final_home,
                    final_away,
                )
                if outcome:
                    row['bet_result'] = outcome
                if payout is not None:
                    payout = round(payout, 2)
                    row['bet_return'] = payout
                    diff = payout - previous_return
                    if abs(diff) > 1e-9:
                        bankroll_delta += diff
                updated = True
            rows.append(row)
    if updated:
        with PREDICTION_HISTORY_PATH.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER)
            writer.writeheader()
            writer.writerows(rows)
        if abs(bankroll_delta) > 1e-9:
            adjust_bankroll(bankroll_delta)
    return updated


def record_bet(
    fixture_id: Any,
    *,
    status_snapshot: Optional[str],
    selection: str,
    bookmaker: Optional[str] = None,
    odd: Optional[float] = None,
    stake: Optional[float] = None,
    timestamp: Optional[str] = None,
    notes: str = '',
) -> bool:
    if is_offline_mode():
        return False
    selection = (selection or '').strip()
    if not selection:
        return False
    _ensure_file()
    normalize_prediction_history()
    try:
        df = pd.read_csv(PREDICTION_HISTORY_PATH)
    except Exception:
        return False
    if df.empty or 'fixture_id' not in df.columns:
        return False
    fixture_token = _normalize_fixture_id(fixture_id)
    if not fixture_token:
        return False
    fixture_series = df['fixture_id'].astype(str).str.strip().apply(_normalize_fixture_id)
    mask = fixture_series == fixture_token
    status_token = str(status_snapshot or '').strip()
    if status_token:
        status_series = df.get('status_snapshot', pd.Series(dtype=str)).fillna('').astype(str).str.strip()
        mask = mask & (status_series == status_token)
    target_indices = df.index[mask]
    if target_indices.empty:
        target_indices = df.index[fixture_series == fixture_token]
        if target_indices.empty:
            return False
    idx = int(target_indices[-1])
    prev_stake_raw = df.at[idx, 'bet_stake'] if 'bet_stake' in df.columns else 0.0
    try:
        prev_stake = float(prev_stake_raw)
    except (TypeError, ValueError):
        prev_stake = 0.0
    if stake is not None:
        try:
            new_stake = float(stake)
        except (TypeError, ValueError):
            new_stake = 0.0
    else:
        new_stake = 0.0

    df.at[idx, 'bet_selection'] = selection
    df.at[idx, 'bet_bookmaker'] = (bookmaker or '').strip()
    df.at[idx, 'bet_timestamp'] = timestamp or _default_timestamp()
    df.at[idx, 'bet_notes'] = notes
    df.at[idx, 'bet_odd'] = float(odd) if odd is not None else pd.NA
    df.at[idx, 'bet_stake'] = new_stake if stake is not None else pd.NA
    if 'bet_result' in df.columns:
        df.at[idx, 'bet_result'] = ''
    if 'bet_return' in df.columns:
        df.at[idx, 'bet_return'] = pd.NA
    df.to_csv(PREDICTION_HISTORY_PATH, index=False)

    delta = prev_stake - new_stake
    if abs(delta) > 1e-9:
        adjust_bankroll(delta)
    return True


def seed_sample_predictions(force: bool = False) -> bool:
    if is_offline_mode():
        return False
    _ensure_file()
    current_df = pd.read_csv(PREDICTION_HISTORY_PATH)
    if not current_df.empty and not force:
        return False
    with PREDICTION_HISTORY_PATH.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        for row in SAMPLE_ROWS:
            writer.writerow(row)
    return True


def _fixture_result(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fixture = entry.get('fixture') or {}
    status = (fixture.get('status') or {}).get('short')
    if status not in FINISHED_STATUS:
        return None
    goals = entry.get('goals') or {}
    teams = entry.get('teams') or {}
    winner = None
    if (teams.get('home') or {}).get('winner') is True:
        winner = 'home'
    elif (teams.get('away') or {}).get('winner') is True:
        winner = 'away'
    else:
        winner = 'draw'
    return {
        'status': status,
        'goals_home': goals.get('home'),
        'goals_away': goals.get('away'),
        'winner': winner,
    }


def sync_prediction_results(limit: int = 40) -> int:
    df = load_prediction_history()
    if df.empty:
        return 0
    pending = df[df['fixture_id'].notna()]
    pending = pending[(pending['result_status'].isna()) | (~pending['result_status'].isin(FINISHED_STATUS))]
    updated = 0
    for fixture in pending['fixture_id'].dropna().unique()[:limit]:
        try:
            fixture_id = int(fixture)
        except (TypeError, ValueError):
            continue
        payload = get_fixture_details(fixture_id) or []
        entry = payload[0] if isinstance(payload, list) and payload else None
        if not isinstance(entry, dict):
            continue
        result = _fixture_result(entry)
        if not result:
            continue
        success = update_outcome(
            fixture_id,
            status=result['status'],
            goals_home=result['goals_home'],
            goals_away=result['goals_away'],
            winner=result['winner'],
        )
        if success:
            updated += 1
    return updated


def over_under_bias(window: int = 200, min_sample: int = 25) -> Dict[str, Any]:
    _ensure_file()
    try:
        df = pd.read_csv(PREDICTION_HISTORY_PATH)
    except Exception:
        return {'bias': 0.0, 'sample': 0, 'predicted': None, 'actual': None}
    if df.empty or 'prob_over_2_5' not in df.columns:
        return {'bias': 0.0, 'sample': 0, 'predicted': None, 'actual': None}

    df = df.copy()
    df['prob_over_2_5'] = pd.to_numeric(df.get('prob_over_2_5'), errors='coerce')
    df['timestamp'] = pd.to_datetime(df.get('timestamp'), errors='coerce')
    df.sort_values('timestamp', inplace=True, na_position='last')

    if window and window > 0:
        df = df.tail(window)

    goals_series = df.get('result_score', pd.Series(dtype=object)).apply(_total_goals_from_score)
    finished_mask = goals_series.notna()
    sample = int(finished_mask.sum())
    actual_rate: Optional[float] = None
    if sample:
        actual_rate = float((goals_series[finished_mask] >= 3).mean())

    pred_series = df.loc[finished_mask, 'prob_over_2_5'].dropna() if sample else df['prob_over_2_5'].dropna()
    pred_mean: Optional[float] = None
    if not pred_series.empty:
        pred_mean = float(pred_series.mean())

    if pred_mean is None or actual_rate is None or sample < min_sample:
        return {
            'bias': 0.0,
            'sample': sample,
            'predicted': pred_mean,
            'actual': actual_rate,
        }

    return {
        'bias': float(actual_rate - pred_mean),
        'sample': sample,
        'predicted': pred_mean,
        'actual': actual_rate,
    }


def export_prediction_dataset(
    output: Union[str, Path, None] = None,
    *,
    drop_na: bool = True,
) -> Path:
    """
    Export the prediction history with engineered features into a CSV dataset.

    Args:
        output: Optional path (str or Path). If omitted, defaults to data/prediction_dataset.csv.
        drop_na: Drop rows with missing key probability fields when True.

    Returns:
        Path of the exported dataset.
    """
    normalize_prediction_history()
    df = load_prediction_history()
    if df.empty:
        raise ValueError("Prediction history is empty, nothing to export.")
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df.get('timestamp'), errors='coerce', utc=True)
    df['fixture_date'] = pd.to_datetime(df.get('fixture_date'), errors='coerce', utc=True)
    for column in FLOAT_COLUMNS:
        df[column] = pd.to_numeric(df.get(column, pd.Series(dtype=float)), errors='coerce')
    if 'feature_home_draw_diff' not in df.columns:
        df['feature_home_draw_diff'] = df['prob_home'] - df['prob_draw']
    if 'feature_home_away_diff' not in df.columns:
        df['feature_home_away_diff'] = df['prob_home'] - df['prob_away']
    if 'feature_over_under_diff' not in df.columns:
        df['feature_over_under_diff'] = df['prob_over_2_5'] - df['prob_under_2_5']
    if 'feature_max_prob' not in df.columns:
        df['feature_max_prob'] = df[['prob_home', 'prob_draw', 'prob_away']].max(axis=1)
    if 'feature_main_confidence_norm' not in df.columns:
        df['feature_main_confidence_norm'] = pd.to_numeric(df.get('main_confidence', pd.Series(dtype=float)), errors='coerce') / 100.0
    if 'feature_total_pick_over' not in df.columns:
        df['feature_total_pick_over'] = df.get('total_pick', pd.Series(dtype=str)).str.contains('over', case=False, na=False).astype(int)
    for column in [
        'feature_lambda_home',
        'feature_lambda_away',
        'elo_home',
        'elo_away',
        'delta_elo',
        'pressure_score',
        'intensity_score',
    ]:
        if column not in df.columns:
            df[column] = np.nan
    if drop_na:
        df.dropna(subset=['prob_home', 'prob_draw', 'prob_away'], inplace=True)
    dataset_path = Path(output) if output is not None else PREDICTION_DATASET_PATH
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dataset_path, index=False)
    return dataset_path

__all__ = [
    'load_prediction_history',
    'append_prediction',
    'upsert_prediction',
    'normalize_prediction_history',
    'update_outcome',
    'record_bet',
    'seed_sample_predictions',
    'sync_prediction_results',
    'over_under_bias',
    'training_progress',
    'PREDICTION_HISTORY_PATH',
    'export_prediction_dataset',
]
