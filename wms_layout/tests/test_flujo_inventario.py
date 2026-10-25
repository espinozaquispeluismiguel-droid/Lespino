from tests.conftest import subir_excel, token

MAESTRO = [
    {"Artículo": "ART-1", "Descripción": "Tablero 18mm", "Nº Paquete": " pkg-001 ", "Cantidad": 25, "UM": "und"},
    {"Artículo": "ART-2", "Descripción": "Perfil 6m", "Nº Paquete": "PKG-002", "Cantidad": "12,5", "UM": "M"},
    {"Artículo": "ART-3", "Descripción": "Bisagra", "Nº Paquete": "000777", "Cantidad": 100, "UM": "UND"},
]


# ------------------------------------------------------------------ autenticación
def test_bloqueo_por_intentos_fallidos(client):
    for _ in range(5):
        r = client.post("/api/v1/auth/login", data={"username": "operario1", "password": "mal"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/login", data={"username": "operario1", "password": "Cambiar123!"})
    assert r.status_code == 423


# ------------------------------------------------------------------ carga Excel
def test_importacion_excel_alias_normalizacion_y_upsert(client, datos):
    adm = token(client, "admin")
    r = subir_excel(client, adm, datos["layout"], MAESTRO)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["insertados"], body["actualizados"], body["filas_con_error"]) == (3, 0, 0)
    assert body["aplicado"] is True

    # Segunda carga: un cambio de cantidad, una fila con error, una duplicada
    filas = [
        {**MAESTRO[0], "Cantidad": 30},
        MAESTRO[1],
        {"Artículo": "ART-9", "Descripción": "", "Nº Paquete": "PKG-009", "Cantidad": "abc"},
        {**MAESTRO[1]},
    ]
    body = subir_excel(client, adm, datos["layout"], filas).json()
    assert body["actualizados"] == 1 and body["sin_cambios"] == 1 and body["filas_con_error"] == 2
    errores = {e["fila"]: e["errores"] for e in body["errores"]}
    assert any("cantidad no numérica" in x for x in errores[4])
    assert any("duplicado" in x for x in errores[5])


def test_importacion_dry_run_y_reemplazar(client, datos):
    adm = token(client, "admin")
    subir_excel(client, adm, datos["layout"], MAESTRO)
    body = subir_excel(client, adm, datos["layout"], MAESTRO[:1], modo="reemplazar", dry_run=True).json()
    assert body["inactivados"] == 2 and body["aplicado"] is False
    body = subir_excel(client, adm, datos["layout"], MAESTRO[:1], modo="reemplazar").json()
    assert body["inactivados"] == 2 and body["aplicado"] is True


def test_importacion_requiere_admin_y_columnas(client, datos):
    op = token(client, "operario1")
    assert subir_excel(client, op, datos["layout"], MAESTRO).status_code == 403
    adm = token(client, "admin")
    r = subir_excel(client, adm, datos["layout"], [{"foo": 1}])
    assert r.status_code == 422 and "Faltan columnas" in r.json()["detail"]


# ------------------------------------------------------------------ validación de paquetes
def _registrar(client, headers, **payload):
    return client.post("/api/v1/inventario/registrar", headers=headers, json=payload)


def test_flujo_completo_validacion(client, datos):
    subir_excel(client, token(client, "admin"), datos["layout"], MAESTRO)
    op1 = token(client, "operario1")
    a1 = datos["calles"]["A1"]

    # 1. Coincide (QR con espacios/minúsculas -> se normaliza igual que en el Excel)
    r = _registrar(client, op1, id_calle=a1, numero_de_paquete="pkg-001", cantidad_contada=25, metodo_ingreso="qr")
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["estado"] == "coincide" and b["coincide"] is True
    assert b["cantidad_esperada"] is None  # conteo ciego para operario
    assert b["estado_calle"] == "en_proceso"
    assert b["avance"]["contados"] == 1 and b["avance"]["total_catalogados"] == 3

    # 2. Diferencia (decimales)
    b = _registrar(client, op1, id_calle=a1, numero_de_paquete="PKG-002", cantidad_contada="12.0").json()
    assert b["estado"] == "diferencia" and b["coincide"] is False

    # 3. No catalogado / sobrante
    b = _registrar(client, op1, id_calle=a1, numero_de_paquete="XYZ-999", cantidad_contada=4,
                   articulo="ART-X", metodo_ingreso="foto_ia", ocr_confianza=87.5).json()
    assert b["estado"] == "no_catalogado" and b["articulo"] == "ART-X"

    # 4. Duplicado -> 409 con contexto
    r = _registrar(client, op1, id_calle=a1, numero_de_paquete="PKG-002", cantidad_contada=12.5)
    assert r.status_code == 409 and r.json()["codigo"] == "paquete_ya_contado"
    assert r.json()["contexto"]["codigo_calle"] == "A1"

    # 5. Reconteo -> sustituye el anterior
    b = _registrar(client, op1, id_calle=a1, numero_de_paquete="PKG-002", cantidad_contada=12.5, reconteo=True).json()
    assert b["estado"] == "coincide" and b["es_reconteo"] is True
    assert b["avance"]["coinciden"] == 2 and b["avance"]["diferencias"] == 0

    # 6. Supervisor ve la cantidad esperada
    sup = token(client, "supervisor")
    b = _registrar(client, sup, id_calle=a1, numero_de_paquete="000777", cantidad_contada=99).json()
    assert float(b["cantidad_esperada"]) == 100 and float(b["diferencia"]) == -1

    # 7. Historial de auditoría
    h = client.get("/api/v1/historial", headers=sup, params={"id_calle": a1}).json()
    tipos = [e["tipo_evento"] for e in h["items"]]
    assert "inicio_conteo" in tipos and "paquete_recontado" in tipos and "paquete_no_catalogado" in tipos
    h = client.get("/api/v1/historial", headers=sup, params={"numero_de_paquete": "pkg-002"}).json()
    assert h["total"] == 2

    # 8. Finalizar calle -> con incidencias (sobrante + diferencia de 000777)
    r = client.post(f"/api/v1/inventario/calles/{a1}/finalizar", headers=op1)
    assert r.status_code == 200 and r.json()["estado"] == "con_incidencias"
    r = _registrar(client, op1, id_calle=a1, numero_de_paquete="NUEVO", cantidad_contada=1)
    assert r.status_code == 409 and r.json()["codigo"] == "calle_cerrada"


def test_operario_sin_asignacion(client, datos):
    op1 = token(client, "operario1")
    r = _registrar(client, op1, id_calle=datos["calles"]["B1"], numero_de_paquete="PKG-001", cantidad_contada=1)
    assert r.status_code == 403 and r.json()["codigo"] == "calle_no_asignada"
    # operario2 tiene A2 asignada directamente (sin equipo)
    op2 = token(client, "operario2")
    r = _registrar(client, op2, id_calle=datos["calles"]["A2"], numero_de_paquete="PKG-001", cantidad_contada=1)
    assert r.status_code == 201


def test_duplicado_entre_calles_del_mismo_layout(client, datos):
    subir_excel(client, token(client, "admin"), datos["layout"], MAESTRO)
    op1, op2 = token(client, "operario1"), token(client, "operario2")
    assert _registrar(client, op1, id_calle=datos["calles"]["A1"], numero_de_paquete="PKG-001",
                      cantidad_contada=25).status_code == 201
    r = _registrar(client, op2, id_calle=datos["calles"]["A2"], numero_de_paquete="PKG-001", cantidad_contada=25)
    assert r.status_code == 409 and r.json()["contexto"]["usuario"] == "Operario Uno"


# ------------------------------------------------------------------ tiempo real
def test_websocket_recibe_eventos(client, datos):
    subir_excel(client, token(client, "admin"), datos["layout"], MAESTRO)
    sup_tok = token(client, "supervisor")["Authorization"].split()[1]
    op1 = token(client, "operario1")
    with client.websocket_connect(f"/ws/layouts/{datos['layout']}?token={sup_tok}") as ws:
        snap = ws.receive_json()
        assert snap["evento"] == "snapshot" and snap["data"]["avance"]["total_catalogados"] == 3
        _registrar(client, op1, id_calle=datos["calles"]["A1"], numero_de_paquete="PKG-002", cantidad_contada=10)
        ev = ws.receive_json()
        assert ev["evento"] == "paquete_registrado"
        assert ev["data"]["cantidad_esperada"] == 12.5  # el supervisor sí la ve
        assert ev["data"]["calle"]["estado"] == "en_proceso" and ev["data"]["calle"]["diferencias"] == 1


def test_websocket_rechaza_operario(client, datos):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    op_tok = token(client, "operario1")["Authorization"].split()[1]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/layouts/{datos['layout']}?token={op_tok}") as ws:
            ws.receive_json()
