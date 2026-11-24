from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(access: str, refresh: str) -> TokenResponse:
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    try:
        return auth_service.register_user(db, body.email, body.password)
    except auth_service.WeakPasswordError as e:
        raise HTTPException(status_code=422, detail=e.errors)
    except auth_service.EmailTakenError:
        raise HTTPException(status_code=409, detail="Email already registered")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("30/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    try:
        access, refresh = auth_service.login_user(db, body.email, body.password)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _tokens(access, refresh)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        access, new_refresh = auth_service.refresh_session(db, body.refresh_token)
    except auth_service.InvalidRefreshError:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _tokens(access, new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
def logout(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    auth_service.logout_session(db, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user