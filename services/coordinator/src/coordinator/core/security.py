from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import jwt
from coordinator.config import settings


def hash_password(password: str) -> str:
    """Hash plaintext password with bcrypt salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    subject: str,
    token_type: str = "user",
    role: str = "operator",
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a signed, expirable JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        minutes = (
            settings.ACCESS_TOKEN_EXPIRE_MINUTES
            if token_type == "user"
            else settings.WORKER_TOKEN_EXPIRE_MINUTES
        )
        expire = now + timedelta(minutes=minutes)

    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.COORDINATOR_SECRET_KEY, algorithm=settings.COORDINATOR_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.COORDINATOR_SECRET_KEY,
        algorithms=[settings.COORDINATOR_ALGORITHM],
    )
