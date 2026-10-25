from pathlib import Path

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import DBAPIError
from fastapi.staticfiles import StaticFiles

from app.api.v1.endpoints import ws
from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = logging.getLogger("wms")


# ---- Errores de infraestructura con mensaje legible (en vez de un 500 genérico)
def _diagnostico_bd(exc: Exception) -> tuple[int, str]:
    t = str(exc).lower()
    if any(k in t for k in ("no such table", "does not exist", "no existe", "undefinedtable", "undefinedcolumn",
                             "no such column")):
        return 500, ("Faltan tablas o columnas en la base de datos. Ejecute: python -m scripts.seed "
                     "(o cargue sql/schema.sql).")
    if any(k in t for k in ("password authentication", "autentificación", "autenticación", "invalidpassword",
                             "role \"", "rol «")):
        return 503, "PostgreSQL rechazó el usuario o la contraseña. Revise DATABASE_URL en .env."
    if "database" in t and ("does not exist" in t or "no existe" in t):
        return 503, "La base de datos indicada en DATABASE_URL no existe. Créela primero."
    if isinstance(exc, OSError) or any(k in t for k in ("connect call failed", "connection refused", "timeout",
                                                         "could not connect", "getaddrinfo")):
        return 503, ("No se puede conectar con la base de datos. Revise que PostgreSQL esté encendido "
                     "y que DATABASE_URL en .env sea correcta (host, puerto).")
    return 500, "Error de base de datos."


@app.exception_handler(OSError)
@app.exception_handler(DBAPIError)
async def _error_bd(request: Request, exc: Exception):
    status_code, detalle = _diagnostico_bd(exc)
    log.exception("Error de base de datos en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=status_code, content={
        "detail": detalle, "error": f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}"})


@app.exception_handler(Exception)
async def _no_controlado(request: Request, exc: Exception):
    log.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={
        "detail": f"Error interno del servidor ({type(exc).__name__}). Revise la consola de uvicorn.",
        "error": str(exc)[:300]})


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws.router)
# Frontend (SPA): http://localhost:8000/app/
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/app", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")


@app.get("/", include_in_schema=False)
async def raiz():
    return RedirectResponse("/app/")


@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "ok"}
