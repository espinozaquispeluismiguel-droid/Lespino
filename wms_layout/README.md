# WMS Layout & Inventario — Backend (FastAPI + PostgreSQL)

Plataforma para gestionar layouts de almacén e inventario por paquete con validación cruzada
contra un maestro cargado desde Excel, y monitorización en tiempo real por WebSocket.

**Estado:** backend y frontend completos para las 5 fases. 16 tests de API (SQLite y PostgreSQL 16),
prueba de concurrencia y recorrido en navegador (Playwright) de los tres roles.

**Interfaz:** `http://localhost:8000/` (redirige a `/app/`). Documentación de la API: `/docs`.

## 1. Estructura de directorios

```
wms_layout/
├── app/
│   ├── main.py                     # FastAPI: routers, CORS, estáticos
│   ├── core/
│   │   ├── config.py               # Settings (.env) con pydantic-settings
│   │   ├── database.py             # Engine/sesión async SQLAlchemy 2.0 (asyncpg)
│   │   └── security.py             # bcrypt + JWT
│   ├── models/                     # ORM (una tabla = una clase)
│   │   ├── base.py                 # Base, naming convention, mixins
│   │   ├── enums.py                # ENUM nativos de PostgreSQL
│   │   ├── organizacion.py         # organizacion, delegacion, usuario
│   │   ├── almacen.py              # layout, area, calle
│   │   ├── equipo.py               # equipo, equipo_usuario, asignacion_calle
│   │   ├── producto.py             # producto, producto_inventario
│   │   └── historial.py            # historial_calle
│   ├── schemas/                    # Pydantic (entrada/salida de la API)
│   ├── services/                   # Lógica de negocio (sin FastAPI)
│   │   ├── excel_import.py         # Carga masiva del maestro
│   │   ├── inventario_service.py   # Validación cruzada de paquetes
│   │   ├── historial_service.py    # Trazabilidad
│   │   ├── ocr_service.py          # Foto de etiqueta -> campos (OpenCV + Tesseract)
│   │   └── normalizacion.py        # Normalización común de nº de paquete
│   ├── websockets/manager.py       # Canales por layout
│   ├── api/
│   │   ├── deps.py                 # get_current_user, require_roles (RBAC)
│   │   └── v1/endpoints/           # auth, productos, inventario, historial, ws
│   └── static/                     # Frontend SPA (HTML + Tailwind compilado + JS sin build)
│       ├── index.html
│       ├── css/                    # tailwind.css (compilado) + app.css
│       ├── vendor/                 # html5-qrcode (local, sin CDN)
│       └── js/
│           ├── app.js              # router hash + menú por rol
│           ├── api.js, ui.js, plano.js
│           └── views/              # login, operario, captura, dashboard, asignaciones,
│                                   # historial, layouts, productos, usuarios
├── frontend/tailwind.input.css     # fuente de Tailwind (tailwind.config.js en la raíz)
├── sql/schema.sql                  # DDL PostgreSQL generado desde los modelos
├── scripts/
│   ├── seed.py                     # Crea tablas + datos de ejemplo
│   └── generar_ddl.py              # Regenera sql/schema.sql
├── tests/                          # pytest (SQLite por defecto o PostgreSQL)
├── Dockerfile, docker-compose.yml, requirements*.txt, .env.example
```

La lógica vive en `services/` y no depende de FastAPI: se puede probar sola y reutilizar
desde tareas en segundo plano o desde la CLI.

## 2. Puesta en marcha

```bash
cp .env.example .env
docker compose up -d db
pip install -r requirements-dev.txt
python -m scripts.seed            # tablas + usuarios admin/supervisor/operario1/operario2 (clave: Cambiar123!)
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

En producción, crear el esquema con `sql/schema.sql` o con Alembic
(`alembic init -t async migrations`, apuntando `target_metadata = app.models.Base.metadata`).

Tests: `pytest` (SQLite) o
`TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host/db_test pytest` (PostgreSQL real).

### En GitHub Codespaces

El repositorio incluye `.devcontainer/`: al crear el Codespace se levantan Python 3.12 y PostgreSQL 16,
se instalan las dependencias (y Tesseract), se crea `.env` y se cargan los datos de prueba (tarda 3-5 min la primera vez).
Después solo hay que arrancar el servidor:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Codespaces publica el puerto 8000 con HTTPS (`https://<nombre>-8000.app.github.dev`), así que la cámara del móvil
funciona. Para abrirlo desde un móvil, en la pestaña **PORTS** cambia la visibilidad del 8000 a **Public**
(cualquiera con el enlace podrá ver la pantalla de login; vuelve a ponerlo en Private al terminar).

## 3. Interfaz web (por rol)

| Rol | Pantallas |
|---|---|
| Operario (móvil) | **Mis calles** → **Captura**: pestañas Manual / Escanear (cámara QR y código de barras) / Foto (OCR). Muestra el resultado al momento (coincide, diferencia o sobrante), avisa de duplicados con opción de reconteo, lista lo contado y permite finalizar la calle |
| Supervisor | **Tiempo real**: KPIs de avance y plano SVG coloreado por estado que se actualiza por WebSocket, con feed de actividad y detalle por calle (reabrir). **Asignaciones**: selección de calles en el plano o en la tabla, asignación a operario o equipo, gestión de equipos. **Historial** con filtros |
| Administrador | Todo lo anterior, más **Layouts** (crear layouts, áreas y calles por rango; arrastrar calles en el plano para colocarlas), **Productos** (importación Excel con validación previa y detalle de errores por fila) y **Usuarios** (alta y desbloqueo) |

Notas:
- **Funciona sin internet**: Tailwind está compilado y el lector QR va incluido. Solo la fuente Roboto
  se pide a Google Fonts; sin conexión se usa la fuente del sistema.
- **La cámara del móvil requiere HTTPS** (o `localhost`). Para probar en la red local:
  `uvicorn app.main:app --host 0.0.0.0 --ssl-keyfile key.pem --ssl-certfile cert.pem`
  (certificado autofirmado con `openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365`),
  o un proxy inverso con certificado. Los lectores USB/Bluetooth funcionan en la pestaña Manual sin HTTPS.
- Si cambias clases de Tailwind en las vistas, recompila el CSS:
  `npx tailwindcss@3.4.17 -c tailwind.config.js -i frontend/tailwind.input.css -o app/static/css/tailwind.css --minify`

## 4. Endpoints

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/v1/auth/login` | — | JWT. Bloqueo tras N intentos fallidos (423) |
| POST | `/api/v1/productos/importar` | admin | Carga Excel (multipart: `id_layout`, `modo`, `dry_run`, `permitir_parcial`, `archivo`) |
| GET | `/api/v1/productos/plantilla` | admin | Plantilla .xlsx |
| POST | `/api/v1/inventario/registrar` | todos | Registrar y validar un paquete (manual / qr / foto_ia) |
| POST | `/api/v1/inventario/ocr` | todos | Foto -> propuesta de campos (no registra) |
| POST | `/api/v1/inventario/calles/{id}/finalizar` | todos* | Cierra la calle: `verificada` o `con_incidencias` |
| GET | `/api/v1/inventario/mis-calles` | todos | Calles asignadas al usuario (directo o por equipo) |
| GET | `/api/v1/inventario/calles/{id}/registros` | todos* | Paquetes contados en la calle |
| POST | `/api/v1/inventario/calles/{id}/reabrir` | supervisor/admin | Reabre una calle cerrada |
| GET/POST | `/api/v1/layouts` | todos / admin | Listar y crear layouts |
| GET | `/api/v1/layouts/{id}` · `/avance` | supervisor/admin | Árbol áreas → calles con estado, asignación y conteos · KPIs |
| POST/DELETE | `/api/v1/layouts/{id}/areas` · `/api/v1/areas/{id}` | admin | Crear y borrar áreas |
| POST | `/api/v1/areas/{id}/calles` | admin | Crear calles (lista o prefijo + rango) |
| PATCH/DELETE | `/api/v1/calles/{id}` | admin | Editar código y coordenadas · borrar |
| POST/DELETE | `/api/v1/asignaciones` · `/{id}` | supervisor/admin | Asignar calles (sustituye la asignación anterior) · quitar |
| GET/POST | `/api/v1/usuarios` · `/{id}/desbloquear` | supervisor/admin · admin | Usuarios de la delegación |
| GET/POST/PUT | `/api/v1/equipos` · `/{id}/miembros` | supervisor/admin | Equipos y sus miembros |
| GET | `/api/v1/auth/me` | todos | Usuario actual |
| GET | `/api/v1/historial` | supervisor/admin | Auditoría con filtros: fecha, usuario, calle, paquete, tipo |
| WS | `/ws/layouts/{id}?token=JWT` | supervisor/admin | Eventos `snapshot`, `paquete_registrado`, `calle_finalizada`, `calle_actualizada`, `calles_asignadas` |

\* Un operario solo puede actuar sobre calles que tenga asignadas, directamente o a través de su equipo.

### Ejemplo: registrar un paquete
```json
POST /api/v1/inventario/registrar
{ "id_calle": 1, "numero_de_paquete": "PKG-002", "cantidad_contada": 12, "metodo_ingreso": "qr" }
```
Respuesta `201`: `estado` (`coincide` | `diferencia` | `no_catalogado`), `coincide`, `mensaje`,
`estado_calle` y `avance` del layout. Si el paquete ya se contó: `409 paquete_ya_contado`, con la
calle, el usuario y la fecha del conteo anterior. Reenviando con `"reconteo": true` se sustituye ese conteo.

## 5. Decisiones de diseño

- **Normalización única del nº de paquete** (`services/normalizacion.py`): se aplica igual en la carga
  Excel, en el QR y en el OCR (quita espacios, pasa a mayúsculas, convierte `123.0` → `123`). Sin esto,
  el cruce falla por detalles de formato.
- **Excel**: se lee con `dtype=str` para conservar los ceros a la izquierda. Acepta alias de cabecera
  (`Nº Paquete`, `Descripción`, `UM`…) e informa del error de cada fila con su número en el Excel.
  Hace upsert por lotes. `modo=reemplazar` pasa a inactivos los productos que no vienen en el archivo,
  `dry_run` valida sin guardar, y un paquete de otro layout se rechaza en lugar de reasignarse.
- **Un conteo vigente por paquete y layout**: lo garantiza el servicio con `pg_advisory_xact_lock` + `SELECT … FOR UPDATE`,
  y un índice único parcial `(id_calle, numero_de_paquete) WHERE vigente` lo refuerza en la BD.
  Los reconteos no borran nada: el registro anterior queda con `vigente=false` y se enlaza en `id_reemplaza_a`.
- **Atomicidad**: el conteo, el cambio de estado de la calle y el `historial_calle` se guardan en un mismo commit.
  El broadcast por WebSocket se envía después del commit, así el dashboard nunca muestra datos revertidos.
- **Conteo ciego** (`CONTEO_CIEGO=true`): el operario ve si el conteo coincide, pero no la cantidad teórica.
  El supervisor sí la recibe.
- **Paquete de otro layout** o inexistente → `no_catalogado` (sobrante), con una observación que lo explica.
- **Aislamiento por delegación**: cada usuario solo ve layouts, calles, usuarios y equipos de su delegación.
- **Una asignación activa por calle**: reasignar desactiva la anterior (queda en el historial).

## 6. Próximos pasos recomendados

1. Con varios workers/réplicas: Redis Pub/Sub en `websockets/manager.py`.
2. Tabla `campana_inventario` para repetir inventarios del mismo layout en el tiempo
   (hoy la unicidad de conteo es por layout).
3. Exportar a Excel el resultado del inventario (diferencias y sobrantes por calle).
4. Refresh tokens y auditoría de la carga Excel (quién subió qué archivo y con qué resultado).
5. Modo sin conexión en la vista operario (cola local y sincronización) para zonas sin cobertura Wi-Fi.
