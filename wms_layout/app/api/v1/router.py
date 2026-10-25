from fastapi import APIRouter

from app.api.v1.endpoints import asignaciones, auth, historial, inventario, layouts, productos, usuarios

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(layouts.router)
api_router.include_router(asignaciones.router)
api_router.include_router(productos.router)
api_router.include_router(inventario.router)
api_router.include_router(historial.router)
