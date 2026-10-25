"""Tests de integración sobre SQLite (aiosqlite). En CI conviene repetirlos con
PostgreSQL real (docker) para cubrir ENUMs nativos y advisory locks."""
import asyncio
import io
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

DB_FILE = ROOT / "tests" / "_test.db"
# TEST_DATABASE_URL=postgresql+asyncpg://... para correr contra PostgreSQL real
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite+aiosqlite:///{DB_FILE}")
os.environ["SECRET_KEY"] = "test-secret-key-de-al-menos-32-bytes!!"
os.environ["CONTEO_CIEGO"] = "true"
os.environ["DB_NULLPOOL"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from scripts.seed import seed  # noqa: E402


async def _reset():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return await seed()


@pytest.fixture()
def datos():
    return asyncio.run(_reset())


@pytest.fixture()
def client(datos):
    with TestClient(app) as c:
        yield c


def token(client: TestClient, username: str) -> dict:
    r = client.post("/api/v1/auth/login", data={"username": username, "password": "Cambiar123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def excel_bytes(filas: list[dict]) -> bytes:
    import pandas as pd

    buf = io.BytesIO()
    pd.DataFrame(filas).to_excel(buf, index=False)
    return buf.getvalue()


def subir_excel(client, headers, id_layout, filas, **form):
    return client.post(
        "/api/v1/productos/importar",
        headers=headers,
        data={"id_layout": str(id_layout), **{k: str(v).lower() for k, v in form.items()}},
        files={"archivo": ("productos.xlsx", excel_bytes(filas),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
