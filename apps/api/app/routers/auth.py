from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user
from app.auth.security import create_access_token, verify_password
from app.db import get_db
from app.models import User, UserRole
from app.schemas.common import TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(
        select(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .where(User.email == form.username)
    )
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou palavra-passe incorretos")
    token = create_access_token(str(user.id), extra={"org": str(user.organization_id)})
    return TokenOut(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=user.organization_id,
        roles=[ur.role.code for ur in user.roles],
    )
