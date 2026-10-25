#!/usr/bin/env bash
# Preparación automática del Codespace (se ejecuta una sola vez al crearlo).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Instalando Tesseract (OCR para el método 'Foto')"
sudo apt-get update -qq && sudo apt-get install -y -qq tesseract-ocr tesseract-ocr-spa >/dev/null || \
  echo "   (Tesseract no se pudo instalar; el resto funciona igual)"

echo "==> Instalando dependencias de Python"
pip install --quiet --upgrade pip
pip install --quiet -r requirements-dev.txt

if [ ! -f .env ]; then
  echo "==> Creando .env"
  cp .env.example .env
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')|" .env
fi

echo "==> Esperando a PostgreSQL"
for i in $(seq 1 30); do
  python - <<'PY' && break
import asyncio, asyncpg, sys
async def main():
    c = await asyncpg.connect("postgresql://wms:wms@localhost:5432/wms_layout", timeout=2)
    await c.close()
try:
    asyncio.run(main())
except Exception:
    sys.exit(1)
PY
  sleep 2
done

echo "==> Creando tablas y datos de prueba"
python -m scripts.seed

cat <<'MSG'

============================================================
 Listo. Para arrancar la aplicación ejecuta:

   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

 y abre el puerto 8000 (pestaña PORTS). Usuarios de prueba:
   admin / supervisor / operario1 / operario2  ->  Cambiar123!
============================================================
MSG
