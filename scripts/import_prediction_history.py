#!/usr/bin/env python3
"""
Importe prediction_history.csv depuis Supabase Storage (bucket 'imports')
puis insère les données dans public.prediction_history.

Améliorations :
- Affiche l’URL signée, le content-type et un extrait du contenu.
- Normalise l’URL renvoyée par Supabase (cas /object/... relatifs).
- Message d’erreur clair si le CSV n’est pas lisible.
"""

import os
import io
import sys
import json
import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

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
    except requests.RequestException as e:
        raise SystemExit(f"Erreur requête vers l'endpoint de signature: {e}")

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
    except requests.RequestException as e:
        raise SystemExit(f"Erreur lors du GET de l'URL signée: {e}")

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
    except Exception as e:
        raise RuntimeError(f"Impossible de parser le CSV: {e}\n(aperçu du contenu: {preview_text[:500]})")
    return df


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    if "timestamp_utc" in df.columns:
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df = df.where(pd.notnull(df), None)
    return df


def insert_dataframe_to_db(df: pd.DataFrame, table: str = "public.prediction_history"):
    if df.empty:
        print("DataFrame vide – rien à insérer.")
        return

    cols = list(df.columns)
    columns_sql = ", ".join([f'"{c}"' for c in cols])
    template = "(" + ", ".join(["%s"] * len(cols)) + ")"
    insert_sql = f"INSERT INTO {table} ({columns_sql}) VALUES %s ON CONFLICT DO NOTHING;"

    records = [tuple(row) for row in df.itertuples(index=False, name=None)]

    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
    except Exception as e:
        raise SystemExit(f"Impossible de se connecter à la DB: {e}")

    try:
        with conn, conn.cursor() as cur:
            execute_values(cur, insert_sql, records, template=template)
        print(f"{len(records)} lignes insérées (ou ignorées si doublons).")
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
    print("Colonnes après normalisation :", ", ".join(df.columns))

    insert_dataframe_to_db(df)
    print("Import terminé.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Erreur:", e)
        sys.exit(1)

