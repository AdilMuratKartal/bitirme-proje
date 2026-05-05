"""
render_backend/api/gateway.py — Firebase JWT Doğrulama

Her korumalı endpoint'te Depends(verify_firebase_token) kullanılır.
Firebase project ID environment variable'dan okunur.
"""

from __future__ import annotations

import os
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer(auto_error=True)

# firebase-admin opsiyonel — SDK kurulu değilse token doğrulama atlanır (dev mode)
try:
    import firebase_admin
    from firebase_admin import auth as fb_auth, credentials

    _FIREBASE_PROJECT_ID  = os.environ.get("FIREBASE_PROJECT_ID", "")
    _FIREBASE_CONFIG_STR  = os.environ.get("FIREBASE_CONFIG_STR", "")

    if _FIREBASE_PROJECT_ID and not firebase_admin._apps:
        if not _FIREBASE_CONFIG_STR:
            # FIREBASE_CONFIG_STR eksikse Firebase baslatilmaz; korunan endpoint'ler 401 doner
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "FIREBASE_CONFIG_STR env var ayarlanmamis — Firebase baslatilmadi"
            )
        else:
            import json as _json
            _cred = credentials.Certificate(_json.loads(_FIREBASE_CONFIG_STR))
            firebase_admin.initialize_app(_cred)

    _FIREBASE_AVAILABLE = True
except ImportError:
    _FIREBASE_AVAILABLE = False


async def verify_firebase_token(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """
    Authorization: Bearer <firebase_id_token> başlığını doğrular.
    Dönüş: decoded token dict (uid, email vb.)
    Firebase Admin SDK yoksa (dev ortamı) doğrulama atlanır.
    """
    if not _FIREBASE_AVAILABLE:
        return {"uid": "dev_user", "email": "dev@localhost"}

    try:
        decoded = fb_auth.verify_id_token(creds.credentials)
        return decoded
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Geçersiz token: {exc}")
