import base64
import hashlib
import os
import time
from urllib.parse import urlencode

import requests
from django.conf import settings


AUTH_BASE = "https://auth.atlassian.com"
API_BASE = "https://api.atlassian.com"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_pkce_pair() -> tuple[str, str]:
    verifier = _b64url(os.urandom(32))
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = _b64url(digest)
    return verifier, challenge


def build_authorize_url(state: str, code_challenge: str) -> str:
    params = {
        "audience": "api.atlassian.com",
        "client_id": settings.ATLASSIAN_CLIENT_ID,
        "scope": settings.ATLASSIAN_SCOPES,
        "redirect_uri": settings.ATLASSIAN_REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_BASE}/authorize?{urlencode(params)}"


def exchange_token(code: str, code_verifier: str) -> dict:
    payload = {
        "grant_type": "authorization_code",
        "client_id": settings.ATLASSIAN_CLIENT_ID,
        "code": code,
        "redirect_uri": settings.ATLASSIAN_REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    if getattr(settings, "ATLASSIAN_CLIENT_SECRET", ""):
        payload["client_secret"] = settings.ATLASSIAN_CLIENT_SECRET
    # Atlassian token endpoint expects x-www-form-urlencoded
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(f"{AUTH_BASE}/oauth/token", data=payload, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    # add calculated expiry timestamp
    if "expires_in" in data:
        data["expires_at_epoch"] = int(time.time()) + int(data["expires_in"])
    return data


def refresh_access_token(refresh_token: str) -> dict:
    payload = {
        "grant_type": "refresh_token",
        "client_id": settings.ATLASSIAN_CLIENT_ID,
        "refresh_token": refresh_token,
    }
    if getattr(settings, "ATLASSIAN_CLIENT_SECRET", ""):
        payload["client_secret"] = settings.ATLASSIAN_CLIENT_SECRET
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(f"{AUTH_BASE}/oauth/token", data=payload, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    if "expires_in" in data:
        data["expires_at_epoch"] = int(time.time()) + int(data["expires_in"])
    return data


def get_accessible_resources(access_token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(f"{API_BASE}/oauth/token/accessible-resources", headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def api_request(access_token: str, method: str, url: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {access_token}"
    headers.setdefault("Accept", "application/json")
    if "json" in kwargs:
        headers.setdefault("Content-Type", "application/json")
    return requests.request(method, url, headers=headers, timeout=30, **kwargs)
