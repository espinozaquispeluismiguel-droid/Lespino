"""Motor y sesión asíncronos de SQLAlchemy 2.0."""
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_es_sqlite = settings.DATABASE_URL.startswith("sqlite")
_sin_pool = _es_sqlite or settings.DB_NULLPOOL

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # Tests: sin pool para no compartir conexiones entre event loops
    **({"poolclass": NullPool} if _sin_pool else {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}),
)

if _es_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_fk(dbapi_conn, _):  # SQLite no aplica FKs por defecto
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
