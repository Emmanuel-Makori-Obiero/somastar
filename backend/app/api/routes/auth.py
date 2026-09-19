from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import hash_password, verify_password, create_access_token, get_current_user
from app.core.errors import api_error
from app.core.rate_limit import login_limiter, register_limiter
from app.db import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserLogin, Token, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=Token)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    register_limiter.ensure_allowed(ip)
    register_limiter.record(ip)

    email = payload.email.lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise api_error(400, "EMAIL_TAKEN", "An account with this email already exists.")
    user = User(name=payload.name, email=email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower()
    key = f"{_client_ip(request)}:{email}"
    login_limiter.ensure_allowed(key)

    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        login_limiter.record(key)
        raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Incorrect email or password.")

    login_limiter.clear(key)
    return Token(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
