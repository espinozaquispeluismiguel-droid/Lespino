"""Usuarios y equipos de la delegación."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cualquier_rol, solo_admin, supervisor_o_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Equipo, EquipoUsuario, RolUsuario, Usuario
from app.schemas.almacen import EquipoIn, EquipoOut, MiembroOut, UsuarioIn, UsuarioOut

router = APIRouter(tags=["Usuarios y equipos"])


def _u(x: Usuario) -> UsuarioOut:
    return UsuarioOut(id=x.id, username=x.username, nombre_completo=x.nombre_completo, email=x.email, rol=x.rol,
                      activo=x.activo, bloqueado=x.bloqueado, ultimo_acceso=x.ultimo_acceso)


@router.get("/auth/me", response_model=UsuarioOut)
async def yo(u: Usuario = Depends(cualquier_rol)):
    return _u(u)


@router.get("/usuarios", response_model=list[UsuarioOut])
async def listar_usuarios(rol: RolUsuario | None = None, db: AsyncSession = Depends(get_db),
                          u: Usuario = Depends(supervisor_o_admin)):
    q = select(Usuario).where(Usuario.id_delegacion == u.id_delegacion)
    if rol:
        q = q.where(Usuario.rol == rol)
    return [_u(x) for x in (await db.scalars(q.order_by(Usuario.nombre_completo))).all()]


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
async def crear_usuario(data: UsuarioIn, db: AsyncSession = Depends(get_db), u: Usuario = Depends(solo_admin)):
    nuevo = Usuario(id_delegacion=u.id_delegacion, username=data.username.strip(), email=data.email or None,
                    nombre_completo=data.nombre_completo.strip(), rol=data.rol,
                    password_hash=hash_password(data.password))
    db.add(nuevo)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "El usuario o email ya existe")
    return _u(nuevo)


@router.post("/usuarios/{id_usuario}/desbloquear", response_model=UsuarioOut)
async def desbloquear(id_usuario: int, db: AsyncSession = Depends(get_db), u: Usuario = Depends(solo_admin)):
    x = await db.get(Usuario, id_usuario)
    if x is None or x.id_delegacion != u.id_delegacion:
        raise HTTPException(404, "Usuario no encontrado")
    x.bloqueado, x.intentos_fallidos, x.bloqueado_hasta = False, 0, None
    await db.commit()
    return _u(x)


async def _equipos(db: AsyncSession, id_delegacion: int, ids: list[int] | None = None) -> list[EquipoOut]:
    q = select(Equipo).where(Equipo.id_delegacion == id_delegacion)
    if ids:
        q = q.where(Equipo.id.in_(ids))
    equipos = (await db.scalars(q.order_by(Equipo.nombre))).all()
    rows = (
        await db.execute(
            select(EquipoUsuario.id_equipo, EquipoUsuario.id_usuario, Usuario.nombre_completo, EquipoUsuario.es_lider)
            .join(Usuario, Usuario.id == EquipoUsuario.id_usuario)
            .where(EquipoUsuario.id_equipo.in_([e.id for e in equipos] or [-1]))
        )
    ).all()
    miembros: dict[int, list[MiembroOut]] = {}
    for id_eq, id_u, nombre, lider in rows:
        miembros.setdefault(id_eq, []).append(MiembroOut(id_usuario=id_u, nombre_completo=nombre, es_lider=lider))
    return [EquipoOut(id=e.id, nombre=e.nombre, activo=e.activo, miembros=miembros.get(e.id, [])) for e in equipos]


@router.get("/equipos", response_model=list[EquipoOut])
async def listar_equipos(db: AsyncSession = Depends(get_db), u: Usuario = Depends(supervisor_o_admin)):
    return await _equipos(db, u.id_delegacion)


async def _validar_miembros(db: AsyncSession, ids: list[int], u: Usuario):
    if not ids:
        return
    validos = set((await db.scalars(select(Usuario.id).where(
        Usuario.id.in_(ids), Usuario.id_delegacion == u.id_delegacion, Usuario.rol == RolUsuario.OPERARIO))).all())
    if set(ids) - validos:
        raise HTTPException(422, f"Usuarios no válidos (deben ser operarios de la delegación): {sorted(set(ids) - validos)}")


@router.post("/equipos", response_model=EquipoOut, status_code=201)
async def crear_equipo(data: EquipoIn, db: AsyncSession = Depends(get_db), u: Usuario = Depends(supervisor_o_admin)):
    await _validar_miembros(db, data.miembros, u)
    eq = Equipo(id_delegacion=u.id_delegacion, nombre=data.nombre.strip())
    db.add(eq)
    await db.flush()
    db.add_all([EquipoUsuario(id_equipo=eq.id, id_usuario=i, es_lider=(n == 0))
                for n, i in enumerate(dict.fromkeys(data.miembros))])
    await db.commit()
    return (await _equipos(db, u.id_delegacion, [eq.id]))[0]


@router.put("/equipos/{id_equipo}/miembros", response_model=EquipoOut)
async def actualizar_miembros(id_equipo: int, miembros: list[int], db: AsyncSession = Depends(get_db),
                              u: Usuario = Depends(supervisor_o_admin)):
    eq = await db.get(Equipo, id_equipo)
    if eq is None or eq.id_delegacion != u.id_delegacion:
        raise HTTPException(404, "Equipo no encontrado")
    await _validar_miembros(db, miembros, u)
    await db.execute(delete(EquipoUsuario).where(EquipoUsuario.id_equipo == id_equipo))
    db.add_all([EquipoUsuario(id_equipo=id_equipo, id_usuario=i, es_lider=(n == 0))
                for n, i in enumerate(dict.fromkeys(miembros))])
    await db.commit()
    return (await _equipos(db, u.id_delegacion, [id_equipo]))[0]
