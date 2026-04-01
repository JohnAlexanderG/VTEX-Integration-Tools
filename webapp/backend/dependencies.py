"""
FastAPI dependencies para autenticación y control de acceso por rol.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import decode_token
from database import get_db
from models import User, UserRole

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Valida el Bearer token y retorna el usuario activo."""
    try:
        payload = decode_token(credentials.credentials)
        user_id: int = int(payload["user_id"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    return user


def require_roles(*roles: UserRole):
    """Genera un Depends que exige que el usuario tenga uno de los roles indicados."""
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Sin permisos para esta acción")
        return user
    return _checker


# Atajos reutilizables
require_admin      = require_roles(UserRole.superadmin, UserRole.admin)
require_superadmin = require_roles(UserRole.superadmin)
require_any        = get_current_user   # cualquier usuario autenticado
