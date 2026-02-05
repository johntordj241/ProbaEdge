#!/usr/bin/env python3
"""
Importe prediction_history.csv depuis Supabase Storage (bucket 'imports')
puis insère les données dans public.prediction_history.

Améliorations :
- Affiche l’URL signée, le content-type et un extrait du contenu.
- Normalise l’URL renvoyée par Supabase (cas /object/... relatifs).
- Message d’erreur clair si le CSV n’est pas lisible.
"""

import io
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import Json, execute_values

from utils.prediction_metrics import ensure_success_flag

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

BUCKET = "imports"
OBJECT_PATH = "prediction_history.csv"
SIGNED_URL_EXPIRES = 60  # secondes
CSV_SEPARATOR = os.getenv("PREDICTION_CSV_SEP", ",")

if not SUPABASE_URL or not SERVICE_ROLE_KEY or not SUPABASE_DB_URL:
    raise SystemExit("Missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_DB_URL in .env")


def get_signed_url(bucket: str, path: str, expires: int = 60) -> str:
    endpoint = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/sign/{bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
    }
    payload = {"expiresIn": expires}
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=15)
    except requests.RequestException as exc:
        raise SystemExit(f"Erreur requête vers l'endpoint de signature: {exc}")

    if resp.status_code != 200:
        try:
            err = resp.json()
        except ValueError:
            err = resp.text
        raise SystemExit(f"Erreur {resp.status_code} lors de la signature: {err}")

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"Réponse non JSON inattendue de /object/sign: {resp.text}")

    signed = data.get("signedURL") or data.get("signed_url") or data.get("signedUrl")
    if not signed:
        raise RuntimeError(f"Unexpected response from /object/sign: {data}")

    if signed.startswith("/storage/"):
        signed = f"{SUPABASE_URL.rstrip('/')}{signed}"
    elif signed.startswith("/object/"):
        signed = f"{SUPABASE_URL.rstrip('/')}/storage/v1{signed}"
    elif signed.startswith("//"):
        signed = "https:" + signed

    return signed


def download_csv_as_df(signed_url: str) -> pd.DataFrame:
    try:
        resp = requests.get(signed_url, timeout=30)
    except requests.RequestException as exc:
        raise SystemExit(f"Erreur lors du GET de l'URL signée: {exc}")

    try:
        resp.raise_for_status()
    except requests.HTTPError:
        body_preview = resp.text[:500]
        raise SystemExit(f"GET failed {resp.status_code}: {body_preview}")

    content_type = resp.headers.get("content-type", "")
    print(f"[DEBUG] content-type: {content_type}")

    preview_bytes = resp.content[:1000]
    preview_text = preview_bytes.decode("utf-8", errors="replace")
    print("[DEBUG] Contenu (début) :")
    print(preview_text)

    if "csv" not in content_type.lower() and "text" not in content_type.lower() and "application/octet-stream" not in content_type.lower():
        print("[WARN] Le content-type ne semble pas être du CSV. Vérifiez que l'objet stocké est bien un fichier CSV.")

    buffer = io.BytesIO(resp.content)
    try:
        df = pd.read_csv(buffer, sep=CSV_SEPARATOR)
    except Exception as exc:
        raise RuntimeError(f"Impossible de parser le CSV: {exc}\n(aperçu du contenu: {preview_text[:500]})")
    return df


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    if "timestamp_utc" in df.columns:
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df = df.where(pd.notnull(df), None)
    return df


RECORD_COLUMNS = [
    "timestamp_utc",
    "fixture_id",
    "league_id",
    "season",
    "home_team",
    "away_team",
    "selection",
    "confidence",
    "status_snapshot",
    "success_flag",
    "bet_stake",
    "bet_odd",
    "bet_return",
    "edge_comment",
    "metadata",
    "created_at",
]
EXCLUDED_METADATA_KEYS = {
    "timestamp",
    "fixture_date",
    "fixture_id",
    "league_id",
    "season",
    "home_team",
    "away_team",
    "main_pick",
    "main_confidence",
    "selection",
    "confidence",
    "status_snapshot",
    "success_flag",
    "bet_stake",
    "bet_odd",
    "bet_return",
    "edge_comment",
    "metadata",
    "created_at",
}


def _parse_timestamp(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        ts = pd.to_datetime(value, utc=True)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts.isoformat()


def _safe_int(value: Any) -> Optional[int]:
    if value is None or pd.isna(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _nonempty_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _serialize_metadata_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            primitive = value.item()
        except Exception:
            primitive = value
        if isinstance(primitive, (int, float, bool, str)):
            return primitive
        try:
            return str(primitive)
        except Exception:
            return None
    return value


def _build_metadata(row: pd.Series) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for key, value in row.items():
        if key in EXCLUDED_METADATA_KEYS:
            continue
        serialized = _serialize_metadata_value(value)
        if serialized is None:
            continue
        metadata[key] = serialized
    return metadata


def _construct_record(row: pd.Series) -> Optional[Dict[str, Any]]:
    timestamp = _parse_timestamp(row.get("timestamp"))
    if not timestamp:
        return None
    fixture_id = _safe_int(row.get("fixture_id"))
    if fixture_id is None:
        return None
    league_id = _safe_int(row.get("league_id"))
    season = _safe_int(row.get("season"))
    home_team = _nonempty_text(row.get("home_team")) or ""
    away_team = _nonempty_text(row.get("away_team")) or ""
    selection = _nonempty_text(row.get("bet_selection")) or _nonempty_text(row.get("main_pick"))
    confidence = _safe_float(row.get("main_confidence"))
    status_snapshot = _nonempty_text(row.get("status_snapshot"))
    success_value = row.get("success_flag")
    if success_value is None or pd.isna(success_value):
        success_flag: Optional[bool] = None
    else:
        success_flag = bool(success_value)
    bet_stake = _safe_float(row.get("bet_stake"))
    bet_odd = _safe_float(row.get("bet_odd"))
    bet_return = _safe_float(row.get("bet_return"))
    edge_comment = _nonempty_text(row.get("edge_comment"))
    metadata = _build_metadata(row)
    record: Dict[str, Any] = {
        "timestamp_utc": timestamp,
        "fixture_id": fixture_id,
        "league_id": league_id,
        "season": season,
        "home_team": home_team,
        "away_team": away_team,
        "selection": selection,
        "confidence": confidence,
        "status_snapshot": status_snapshot,
        "success_flag": success_flag,
        "bet_stake": bet_stake,
        "bet_odd": bet_odd,
        "bet_return": bet_return,
        "edge_comment": edge_comment,
        "metadata": metadata or None,
        "created_at": timestamp,
    }
    return record


def _prepare_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        record = _construct_record(row)
        if record:
            records.append(record)
    return records


def insert_records_to_db(records: List[Dict[str, Any]], table: str = "public.prediction_history"):
    if not records:
        print("Aucun enregistrement à insérer.")
        return

    columns = RECORD_COLUMNS
    columns_sql = ", ".join([f'"{c}"' for c in columns])
    template = "(" + ", ".join(["%s"] * len(columns)) + ")"
    insert_sql = f"INSERT INTO {table} ({columns_sql}) VALUES %s ON CONFLICT DO NOTHING;"

    values = []
    for record in records:
        row_values = []
        for col in columns:
            value = record.get(col)
            if col == "metadata" and isinstance(value, dict):
                value = Json(value)
            row_values.append(value)
        values.append(tuple(row_values))

    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
    except Exception as exc:
        raise SystemExit(f"Impossible de se connecter à la DB: {exc}")

    try:
        with conn, conn.cursor() as cur:
            execute_values(cur, insert_sql, values, template=template)
        print(f"{len(values)} lignes insérées (ou ignorées si doublons).")
    finally:
        conn.close()


def main():
    print("Téléchargement du CSV depuis Supabase Storage...")
    signed = get_signed_url(BUCKET, OBJECT_PATH, expires=SIGNED_URL_EXPIRES)
    print("[DEBUG] Signed URL:", signed)

    df = download_csv_as_df(signed)
    print(f"Nombre de lignes CSV (y compris header) : {len(df) + 1}")
    print("Premières lignes du CSV :")
    print(df.head())
    print("Colonnes CSV :", ", ".join(df.columns))

    df = normalize_df(df)
    df = ensure_success_flag(df)
    print("Colonnes après normalisation :", ", ".join(df.columns))

    records = _prepare_records(df)
    print(f"{len(records)} enregistrements prêts pour l'insertion.")

    insert_records_to_db(records)
    print("Import terminé.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Erreur:", exc)
        sys.exit(1)
