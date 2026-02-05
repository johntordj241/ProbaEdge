#!/usr/bin/env python3
"""
Debug rapide de Supabase Storage :
1. Liste les buckets
2. Liste les objets d’un bucket donné
3. Génère une URL signée pour prediction_history.csv
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SERVICE_ROLE:
    raise SystemExit("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant")

def call(api: str, method: str = "GET", **kwargs) -> requests.Response:
    url = f"{SUPABASE_URL.rstrip('/')}{api}"
    headers = kwargs.pop("headers", {})
    headers["apikey"] = SERVICE_ROLE
    headers["Authorization"] = f"Bearer {SERVICE_ROLE}"
    resp = requests.request(method, url, headers=headers, **kwargs)
    print(f"{method} {url} => {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text)  # détail en cas d’erreur
        resp.raise_for_status()
    return resp

# 1) lister les buckets
call("/storage/v1/bucket")

# 2) lister les objets du bucket `imports`
call(
    "/storage/v1/object/list/imports",
    method="POST",
    json={"prefix": "", "limit": 20},
)

# 3) signer prediction_history.csv pour 60 s
call(
    "/storage/v1/object/sign/imports/prediction_history.csv",
    method="POST",
    json={"expiresIn": 60},
)
