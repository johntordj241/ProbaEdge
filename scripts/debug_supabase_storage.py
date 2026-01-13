import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SERVICE_ROLE:
    raise SystemExit("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant")


def call(api, method="GET", **kwargs):
    url = f"{SUPABASE_URL.rstrip('/')}{api}"
    headers = kwargs.pop("headers", {})
    headers["apikey"] = SERVICE_ROLE
    headers["Authorization"] = f"Bearer {SERVICE_ROLE}"
    resp = requests.request(method, url, headers=headers, **kwargs)
    print(f"{method} {url} => {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text)
    return resp


# 1) lister les buckets
call("/storage/v1/bucket")

# 2) lister les objets du bucket imports
call(
    "/storage/v1/object/list/imports",
    method="POST",
    json={"prefix": "", "limit": 20},
)

# 3) tenter de signer prediction_history.csv (avec payload JSON)
call(
    "/storage/v1/object/sign/imports/prediction_history.csv",
    method="POST",
    json={"expiresIn": 60},
)
