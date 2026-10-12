from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from coordinator.config import settings
from coordinator.db.session import get_db
from coordinator.models.user import User
from coordinator.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from coordinator.core.security import hash_password, verify_password, create_access_token
from coordinator.core.auth import get_current_user, get_optional_current_user
from coordinator.core.rate_limit import check_login_rate_limit, check_registration_rate_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user operator/admin",
)
async def register_user(
    payload: UserCreate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    _rate_limit: None = Depends(check_registration_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user account."""
    # Enforce role hierarchy: only an existing admin can assign the 'admin' role
    if payload.role == "admin":
        count_stmt = select(func.count(User.id))
        user_count = (await db.execute(count_stmt)).scalar() or 0
        # If users already exist and requester is not authenticated as admin, forbid privilege escalation
        if user_count > 0 and (not current_user or current_user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative role cannot be self-assigned on public registration.",
            )

    # Check if username or email already taken
    stmt = select(User).where((User.username == payload.username) | (User.email == payload.email))
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered.",
        )

    assigned_role = payload.role

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=assigned_role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and obtain JWT access token",
)
async def login_user(
    payload: UserLogin,
    _rate_limit: None = Depends(check_login_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user with username and password."""
    stmt = select(User).where(User.username == payload.username)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    token = create_access_token(
        subject=user.id,
        token_type="user",
        role=user.role,
        expires_delta=timedelta(minutes=expires_minutes),
        extra_claims={"username": user.username},
    )

    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in_seconds=expires_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_my_profile(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return authenticated user profile."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
