"""Auth0 JWT middleware — protects API routes when AUTH0_DOMAIN is configured."""
import httpx
from functools import lru_cache
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from backend.config import AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_AUDIENCE

_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch Auth0 JWKS (cached)."""
    resp = httpx.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json", timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def _verify_token(token: str) -> dict:
    jwks = _get_jwks()
    header = jwt.get_unverified_header(token)
    key = next((k for k in jwks["keys"] if k["kid"] == header.get("kid")), None)
    if not key:
        raise HTTPException(status_code=401, detail="Invalid token key")

    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=AUTH0_AUDIENCE,
        issuer=f"https://{AUTH0_DOMAIN}/",
    )


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """FastAPI dependency — verifies Auth0 JWT. Pass-through if Auth0 not configured."""
    if not AUTH0_DOMAIN:
        return {"sub": "anonymous"}  # Auth0 not configured — allow all

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = _verify_token(credentials.credentials)
        return payload
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
