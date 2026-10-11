import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.config import settings
from coordinator.db.session import get_db
from coordinator.models.user import User
from coordinator.models.worker import Worker
from coordinator.core.security import decode_token

logger = logging.getLogger("coordinator.auth")
security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate user JWT token and return active user object."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is not authorized for user access",
        )

    user_id = payload.get("sub")
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found",
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforce admin privileges."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required",
        )
    return current_user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Optionally resolve current user if bearer credentials provided."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


async def get_current_worker(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> Worker:
    """Validate worker JWT token and return active worker record."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Worker authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Worker token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "worker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is not authorized for worker actions",
        )

    worker_id = payload.get("sub")
    stmt = select(Worker).where(Worker.worker_id == worker_id)
    result = await db.execute(stmt)
    worker = result.scalar_one_or_none()

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_id}' not found",
        )

    if worker.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker credentials have been revoked",
        )

    return worker


async def verify_worker_registration_auth(
    x_worker_token: Optional[str] = Header(None, alias="X-Worker-Auth-Token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> bool:
    """Verify authorization to register a worker."""
    # 1. Check development pre-shared token if allowed
    if x_worker_token and x_worker_token == settings.WORKER_DEV_AUTH_TOKEN:
        return True

    # 2. Check if bearer token matches dev token
    if credentials and credentials.credentials == settings.WORKER_DEV_AUTH_TOKEN:
        return True

    # 3. Check if bearer token is a valid operator or admin user JWT
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("type") == "user":
                return True
        except jwt.PyJWTError:
            pass

    # Reject if no valid credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid worker registration credentials required (X-Worker-Auth-Token or Bearer token)",
    )
