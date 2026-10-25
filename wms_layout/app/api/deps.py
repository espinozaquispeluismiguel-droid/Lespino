"""Dependencias comunes: usuario autenticado y control de roles (RBAC)."""
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models import RolUsuario, Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o sesión expirada",
    headers={"WWW-Authenticate": "Bearer"},
)


async def usuario_desde_token(token: str, db: AsyncSession) -> Usuario:
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _401
    usuario = await db.get(Usuario, user_id)
    if usuario is None or not usuario.activo or usuario.bloqueado:
        raise _401
    return usuario


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> Usuario:
    return await usuario_desde_token(token, db)


def require_roles(*roles: RolUsuario) -> Callable:
    async def _checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permisos para esta operación")
        return usuario

    return _checker


solo_admin = require_roles(RolUsuario.ADMINISTRADOR)
supervisor_o_admin = require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.SUPERVISOR)
cualquier_rol = require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.SUPERVISOR, RolUsuario.OPERARIO)
