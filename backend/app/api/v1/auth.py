from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user, make_token, verify_password
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    # Plain str — full EmailStr validation rejects reserved TLDs like
    # `.local`, which the demo accounts use. The downstream lookup
    # against the DB enforces existence + bcrypt verifies the password,
    # so we don't need strict syntax validation here.
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=512)


class LoginOut(BaseModel):
    token: str
    role: str
    user_id: str
    full_name: str


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> LoginOut:
    user = db.query(User).filter(User.email == body.email.lower()).one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        # Always log failed auth attempts.
        log_event(
            db,
            actor_id=None,
            actor_role=None,
            action="auth.login_failed",
            resource_type="user",
            resource_id=body.email,
            request_id=request.headers.get("x-request-id"),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    token = make_token(user.id, user.role)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        request_id=request.headers.get("x-request-id"),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return LoginOut(token=token, role=user.role, user_id=str(user.id), full_name=user.full_name)


class MeOut(BaseModel):
    user_id: str
    email: str
    role: str
    full_name: str


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user)) -> MeOut:
    return MeOut(user_id=str(user.id), email=user.email, role=user.role, full_name=user.full_name)
