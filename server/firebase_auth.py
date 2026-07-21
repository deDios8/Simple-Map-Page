"""Mints Google OAuth2 access tokens for the server's Firebase service account.

Realtime Database REST calls authenticated with a token from a service
account that has the Firebase Admin role bypass Security Rules entirely -
the same way the firebase-admin SDK does. See:
https://firebase.google.com/docs/reference/rest/database#section-rest-auth
"""

import os
import pathlib
import threading

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

_SCOPES = [
    "https://www.googleapis.com/auth/firebase.database",
    "https://www.googleapis.com/auth/userinfo.email",
]

_KEY_PATH = pathlib.Path(
    os.environ.get(
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        pathlib.Path(__file__).parent / "serviceAccountKey.json",
    )
)

_lock = threading.Lock()
_credentials = None


def _load_credentials():
    global _credentials
    if _credentials is None:
        if not _KEY_PATH.exists():
            raise RuntimeError(
                f"Firebase service account key not found at {_KEY_PATH}. "
                "Download one from Firebase Console > Project Settings > "
                "Service accounts > Generate new private key, then save it "
                "there or point FIREBASE_SERVICE_ACCOUNT_PATH at it."
            )
        _credentials = service_account.Credentials.from_service_account_file(
            str(_KEY_PATH), scopes=_SCOPES
        )
    return _credentials


def auth_headers() -> dict[str, str]:
    """Return an Authorization header with a valid, auto-refreshed bearer token."""
    with _lock:
        credentials = _load_credentials()
        if not credentials.valid:
            credentials.refresh(GoogleAuthRequest())
        return {"Authorization": f"Bearer {credentials.token}"}
