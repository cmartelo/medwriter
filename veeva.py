import threading
import time
from dataclasses import dataclass

import requests
from config import VEEVA_VAULT_URL, VEEVA_USERNAME, VEEVA_PASSWORD

API_VERSION = "v26.1"

_STOP_WORDS = {
    "what", "are", "the", "is", "a", "an", "in", "of", "for", "with",
    "about", "how", "does", "do", "can", "will", "to", "and", "or",
    "related", "available", "information", "please", "tell", "me",
    "regarding", "on", "at", "by", "from", "their", "its",
}


def _keywords(query: str) -> str:
    """Extract meaningful search terms from a natural-language question."""
    words = [w.strip("?.,!") for w in query.lower().split()]
    keywords = [w for w in words if w and w not in _STOP_WORDS]
    return " ".join(keywords) if keywords else query


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
        f"SELECT id, name__v, document_number__v, major_version_number__v, minor_version_number__v "
        f"FROM documents "
        f"FIND('{safe_query}') "
        f"LIMIT {max_results}"
    )
    url = f"{VEEVA_VAULT_URL}/api/{API_VERSION}/query"
    resp = requests.get(url, params={"q": vql}, headers={
        "Authorization": session_id,
        "Accept": "application/json",
    }, timeout=20)
    resp.raise_for_status()
    body = resp.json()
    if body.get("responseStatus") not in ("SUCCESS", "WARNING"):
        raise RuntimeError(f"Veeva query failed: {body.get('errors', body)}")

    docs = []
    for record in body.get("data", []):
        doc_id = record.get("id", "")
        docs.append({
            "id": doc_id,
            "name": record.get("name__v", ""),
            "document_number": record.get("document_number__v", ""),
            "major_version": record.get("major_version_number__v", 1),
            "minor_version": record.get("minor_version_number__v", 0),
            "url": f"{VEEVA_VAULT_URL}/ui/#doc_info/{doc_id}",
        })
    return docs


_SESSION_TTL = 25 * 60  # Veeva sessions last 30 min; refresh at 25


@dataclass
class _VeevaSession:
    session_id: str = ""
    expires_at: float = 0.0


_session = _VeevaSession()
_lock = threading.Lock()


def get_session() -> str:
    """Return a valid cached Veeva session_id, re-authenticating if expired."""
    with _lock:
        if time.monotonic() < _session.expires_at:
            return _session.session_id
        sid = authenticate()
        _session.session_id = sid
        _session.expires_at = time.monotonic() + _SESSION_TTL
        return sid


def search_veeva_auto(query: str, max_results: int = 5) -> list[dict]:
    """search_veeva with automatic session management (used by MCP server)."""
    sid = get_session()
    kw_query = _keywords(query)
    try:
        return search_veeva(kw_query, sid, max_results)
    except RuntimeError as exc:
        if "INVALID_SESSION_ID" in str(exc) or "401" in str(exc):
            with _lock:
                _session.expires_at = 0.0  # force refresh on next call
            return search_veeva(kw_query, get_session(), max_results)
        raise


def get_document_content(doc_id: int | str, major_version: int = 1, minor_version: int = 0) -> str:
    """Retrieve plain text of a Veeva Vault document using the version text endpoint."""
    sid = get_session()
    url = f"{VEEVA_VAULT_URL}/api/{API_VERSION}/objects/documents/{doc_id}/versions/{major_version}/{minor_version}/text"
    resp = requests.get(url, headers={"Authorization": sid, "Accept": "text/plain"}, timeout=30)
    resp.raise_for_status()
    return resp.text.strip()
