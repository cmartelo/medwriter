import requests
from urllib.parse import quote
from config import VEEVA_VAULT_URL, VEEVA_USERNAME, VEEVA_PASSWORD

API_VERSION = "v24.1"


def authenticate() -> str:
    url = f"{VEEVA_VAULT_URL}/api/{API_VERSION}/auth"
    resp = requests.post(url, data={
        "username": VEEVA_USERNAME,
        "password": VEEVA_PASSWORD,
    }, timeout=15)
    resp.raise_for_status()
    body = resp.json()
    if body.get("responseStatus") != "SUCCESS":
        raise RuntimeError(f"Veeva auth failed: {body.get('errors', body)}")
    return body["sessionId"]


def search_veeva(query: str, session_id: str, max_results: int = 5) -> list[dict]:
    safe_query = query.replace("'", "''")
    vql = (
        f"SELECT id, name__v, title__v, document_number__v "
        f"FROM documents "
        f"WHERE name__v CONTAINS ('{safe_query}') "
        f"LIMIT {max_results}"
    )
    url = f"{VEEVA_VAULT_URL}/api/{API_VERSION}/query"
    resp = requests.get(url, params={"q": vql}, headers={
        "Authorization": session_id,
        "Accept": "application/json",
    }, timeout=20)
    resp.raise_for_status()
    body = resp.json()
    if body.get("responseStatus") != "SUCCESS":
        raise RuntimeError(f"Veeva query failed: {body.get('errors', body)}")

    docs = []
    for record in body.get("data", []):
        docs.append({
            "id": record.get("id", ""),
            "title": record.get("title__v", record.get("name__v", "")),
            "document_number": record.get("document_number__v", ""),
            "summary": _fetch_summary(record.get("id", ""), session_id),
        })
    return docs


def _fetch_summary(doc_id: str, session_id: str) -> str:
    if not doc_id:
        return ""
    url = f"{VEEVA_VAULT_URL}/api/{API_VERSION}/objects/documents/{doc_id}"
    try:
        resp = requests.get(url, headers={
            "Authorization": session_id,
            "Accept": "application/json",
        }, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        fields = body.get("document", {})
        return fields.get("description__v", "") or fields.get("abstract__v", "")
    except Exception:
        return ""
