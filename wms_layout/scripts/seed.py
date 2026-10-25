"""Crea las tablas (solo desarrollo; en producción use Alembic) y datos de ejemplo.

    python -m scripts.seed
"""
import asyncio

from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import (
    Area,
    AsignacionCalle,
    Base,
    Calle,
    Delegacion,
    Equipo,
    EquipoUsuario,
    EstadoCalle,
    Layout,
    Organizacion,
    RolUsuario,
    Usuario,
)


async def crear_tablas() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed() -> dict | None:
    async with SessionLocal() as db:
        # Idempotente: si ya hay usuarios, no duplica nada
        if await db.scalar(select(Usuario.id).limit(1)) is not None:
            print("La base de datos ya tiene datos: no se crean datos de ejemplo.")
            return None
        org = Organizacion(nombre="Alsina", identificador_fiscal="B00000000")
        dele = Delegacion(organizacion=org, nombre="Lima - Central")
        db.add_all([org, dele])
        await db.flush()

        def u(username, rol, nombre):
            return Usuario(
                id_delegacion=dele.id, username=username, nombre_completo=nombre,
                password_hash=hash_password("Cambiar123!"), rol=rol,
            )

        admin = u("admin", RolUsuario.ADMINISTRADOR, "Administrador")
        sup = u("supervisor", RolUsuario.SUPERVISOR, "Supervisor Turno A")
        op1 = u("operario1", RolUsuario.OPERARIO, "Operario Uno")
        op2 = u("operario2", RolUsuario.OPERARIO, "Operario Dos")
        db.add_all([admin, sup, op1, op2])
        await db.flush()

        layout = Layout(id_delegacion=dele.id, nombre="Almacén Principal", id_usuario_creador=admin.id)
        muro = Area(layout=layout, nombre="Muro", color="#8A1538")
        andamio = Area(layout=layout, nombre="Andamio", color="#555555")
        db.add_all([layout, muro, andamio])
        await db.flush()

        calles = [
            Calle(id_area=muro.id, codigo=c, coord_x=i * 10, coord_y=0, ancho=8, alto=40)
            for i, c in enumerate(["A1", "A2"])
        ] + [Calle(id_area=andamio.id, codigo="B1", coord_x=0, coord_y=60, ancho=40, alto=8)]
        db.add_all(calles)

        equipo = Equipo(id_delegacion=dele.id, nombre="Equipo Rojo")
        db.add(equipo)
        await db.flush()
        db.add(EquipoUsuario(id_equipo=equipo.id, id_usuario=op1.id, es_lider=True))

        # A1 -> equipo (op1); A2 -> op2 directo; B1 sin asignar
        db.add_all([
            AsignacionCalle(id_calle=calles[0].id, id_equipo=equipo.id, id_usuario_asignador=sup.id),
            AsignacionCalle(id_calle=calles[1].id, id_usuario=op2.id, id_usuario_asignador=sup.id),
        ])
        calles[0].estado = calles[1].estado = EstadoCalle.ASIGNADA
        await db.commit()
        return {
            "layout": layout.id, "calles": {c.codigo: c.id for c in calles}, "equipo": equipo.id,
            "usuarios": {x.username: x.id for x in (admin, sup, op1, op2)},
        }


async def main() -> None:
    await crear_tablas()
    print(await seed())


if __name__ == "__main__":
    asyncio.run(main())
