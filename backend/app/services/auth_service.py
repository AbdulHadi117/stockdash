import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.password_policy import validate_password
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    utcnow,
    verify_password,
)
from app.models import RefreshToken, User


class WeakPasswordError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors


class EmailTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshError(Exception):
    pass


def register_user(db: Session, email: str, password: str) -> User:
    errors = validate_password(password, email)
    if errors:
        raise WeakPasswordError(errors)
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailTakenError()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    now = utcnow()
    if user is None:
        verify_password(password, DUMMY_HASH)
        raise InvalidCredentialsError()
    if user.locked_until and user.locked_until > now:
        verify_password(password, DUMMY_HASH)
        raise InvalidCredentialsError()

    ok = verify_password(password, user.password_hash)
    if not ok or not user.is_active:
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
        db.commit()
        raise InvalidCredentialsError()

    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return user


def _issue_tokens(db: Session, user: User, family_id: str) -> tuple[str, str]:
    raw, hashed = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=hashed,
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    return create_access_token(user.id), raw


def login_user(db: Session, email: str, password: str) -> tuple[str, str]:
    user = authenticate(db, email, password)
    return _issue_tokens(db, user, uuid.uuid4().hex)


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id)
        .values(revoked=True)
    )
    db.commit()


def refresh_session(db: Session, raw_token: str) -> tuple[str, str]:
    now = utcnow()
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if token is None or token.revoked or token.expires_at <= now:
        db.rollback()
        raise InvalidRefreshError()

    if token.used_at is not None:
        age = (now - token.used_at).total_seconds()
        if age > settings.refresh_reuse_grace_seconds:
            _revoke_family(db, token.family_id)  # reuse after grace: treat as theft
        else:
            db.rollback()
        raise InvalidRefreshError()

    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        db.rollback()
        raise InvalidRefreshError()

    token.used_at = now
    return _issue_tokens(db, user, token.family_id)


def logout_session(db: Session, raw_token: str) -> None:
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    if token is not None:
        _revoke_family(db, token.family_id)