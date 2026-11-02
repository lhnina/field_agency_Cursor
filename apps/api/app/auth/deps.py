from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.security import decode_token
from app.db import get_db
from app.models import Role, User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas") from exc

    user = db.scalar(
        select(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .where(User.id == user_id, User.is_active.is_(True))
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizador inativo ou inexistente")
    return user


def require_roles(*codes: str):
    def _checker(user: User = Depends(get_current_user)) -> User:
        user_codes = {ur.role.code for ur in user.roles}
        if not user_codes.intersection(set(codes)) and "ADMINISTRADOR" not in user_codes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissão")
        return user

    return _checker


def org_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    return user.organization_id
