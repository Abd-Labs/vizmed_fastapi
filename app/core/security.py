# app/core/security.py

from fastapi import Header, HTTPException, Depends
from app.core.config import settings

API_KEYS = set(settings.API_KEYS)  # Use a set for faster lookups

async def api_key_authentication(x_api_key: str = Header(None)):
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="x-api-key header is missing")
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API key")
