"""Fase 1: login con bloqueo por intentos fallidos."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models import Usuario

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str
    nombre: str
    id_usuario: int


@router.post("/login", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    ahora = datetime.now(timezone.utc)
    usuario = await db.scalar(select(Usuario).where(Usuario.username == form.username.strip()))

    # Mensaje genérico: no revelar si el usuario existe
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")
    if usuario is None or not usuario.activo:
        raise error

    if usuario.bloqueado:
        hasta = usuario.bloqueado_hasta
        if hasta is not None and hasta.tzinfo is None:
            hasta = hasta.replace(tzinfo=timezone.utc)
        if hasta is None or hasta > ahora:
            raise HTTPException(
                status.HTTP_423_LOCKED,
                "Usuario bloqueado por intentos fallidos"
                + (f" hasta {hasta.isoformat()}" if hasta else ". Contacte con un administrador."),
            )
        usuario.bloqueado, usuario.intentos_fallidos, usuario.bloqueado_hasta = False, 0, None

    if not verify_password(form.password, usuario.password_hash):
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= settings.MAX_INTENTOS_FALLIDOS:
            usuario.bloqueado = True
            usuario.bloqueado_hasta = ahora + timedelta(minutes=settings.MINUTOS_BLOQUEO)
        await db.commit()
        raise error

    usuario.intentos_fallidos = 0
    usuario.ultimo_acceso = ahora
    await db.commit()
    token = create_access_token(str(usuario.id), usuario.rol.value, {"del": usuario.id_delegacion})
    return TokenOut(access_token=token, rol=usuario.rol.value, nombre=usuario.nombre_completo, id_usuario=usuario.id)
