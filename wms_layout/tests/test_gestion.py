from tests.conftest import subir_excel, token
from tests.test_flujo_inventario import MAESTRO


def test_crud_layout_areas_calles(client):
    adm = token(client, "admin")
    r = client.post("/api/v1/layouts", headers=adm, json={"nombre": "Almacén Norte"})
    assert r.status_code == 201
    lid = r.json()["id"]
    assert client.post("/api/v1/layouts", headers=adm, json={"nombre": "Almacén Norte"}).status_code == 409

    area = client.post(f"/api/v1/layouts/{lid}/areas", headers=adm, json={"nombre": "Muro", "color": "#8A1538"}).json()
    calles = client.post(f"/api/v1/areas/{area['id']}/calles", headers=adm,
                         json={"prefijo": "c", "desde": 1, "hasta": 5}).json()
    assert [c["codigo"] for c in calles] == ["C1", "C2", "C3", "C4", "C5"]
    assert calles[1]["coord_x"] > calles[0]["coord_x"]
    r = client.post(f"/api/v1/areas/{area['id']}/calles", headers=adm, json={"codigos": ["C3", "C9"]})
    assert r.status_code == 409

    r = client.patch(f"/api/v1/calles/{calles[0]['id']}", headers=adm, json={"codigo": "c1b", "coord_y": 99})
    assert r.json()["codigo"] == "C1B" and r.json()["coord_y"] == 99
    assert client.delete(f"/api/v1/calles/{calles[4]['id']}", headers=adm).status_code == 204

    det = client.get(f"/api/v1/layouts/{lid}", headers=adm).json()
    assert len(det["areas"][0]["calles"]) == 4
    lista = client.get("/api/v1/layouts", headers=adm).json()
    assert {l["nombre"]: l["n_calles"] for l in lista}["Almacén Norte"] == 4
    # operario no puede crear
    assert client.post("/api/v1/layouts", headers=token(client, "operario1"), json={"nombre": "X"}).status_code == 403


def test_asignacion_y_mis_calles(client, datos):
    sup = token(client, "supervisor")
    b1 = datos["calles"]["B1"]
    op2 = token(client, "operario2")
    assert all(c["id_calle"] != b1 for c in client.get("/api/v1/inventario/mis-calles", headers=op2).json())

    r = client.post("/api/v1/asignaciones", headers=sup, json={"ids_calle": [b1], "id_usuario": datos["usuarios"]["operario2"]})
    assert r.status_code == 201
    mias = client.get("/api/v1/inventario/mis-calles", headers=op2).json()
    assert {c["codigo"] for c in mias} == {"A2", "B1"}

    det = client.get(f"/api/v1/layouts/{datos['layout']}", headers=sup).json()
    b1_det = next(c for a in det["areas"] for c in a["calles"] if c["id"] == b1)
    assert b1_det["estado"] == "asignada" and b1_det["asignacion"]["usuario"] == "Operario Dos"

    # reasignar a equipo sustituye la asignación anterior
    client.post("/api/v1/asignaciones", headers=sup, json={"ids_calle": [b1], "id_equipo": datos["equipo"]})
    assert {c["codigo"] for c in client.get("/api/v1/inventario/mis-calles", headers=op2).json()} == {"A2"}
    assert "B1" in {c["codigo"] for c in client.get("/api/v1/inventario/mis-calles", headers=token(client, "operario1")).json()}

    # desasignar -> pendiente
    det = client.get(f"/api/v1/layouts/{datos['layout']}", headers=sup).json()
    aid = next(c for a in det["areas"] for c in a["calles"] if c["id"] == b1)["asignacion"]["id"]
    assert client.delete(f"/api/v1/asignaciones/{aid}", headers=sup).status_code == 204
    det = client.get(f"/api/v1/layouts/{datos['layout']}", headers=sup).json()
    assert next(c for a in det["areas"] for c in a["calles"] if c["id"] == b1)["estado"] == "pendiente"

    # no se asigna a supervisores
    r = client.post("/api/v1/asignaciones", headers=sup, json={"ids_calle": [b1], "id_usuario": datos["usuarios"]["supervisor"]})
    assert r.status_code == 422


def test_registros_y_reabrir(client, datos):
    subir_excel(client, token(client, "admin"), datos["layout"], MAESTRO)
    op1, sup = token(client, "operario1"), token(client, "supervisor")
    a1 = datos["calles"]["A1"]
    client.post("/api/v1/inventario/registrar", headers=op1,
                json={"id_calle": a1, "numero_de_paquete": "PKG-001", "cantidad_contada": 20})
    regs = client.get(f"/api/v1/inventario/calles/{a1}/registros", headers=op1).json()
    assert len(regs) == 1 and regs[0]["cantidad_esperada"] is None and regs[0]["usuario"] == "Operario Uno"
    regs = client.get(f"/api/v1/inventario/calles/{a1}/registros", headers=sup).json()
    assert float(regs[0]["cantidad_esperada"]) == 25
    # operario2 no ve A1
    assert client.get(f"/api/v1/inventario/calles/{a1}/registros", headers=token(client, "operario2")).status_code == 403

    client.post(f"/api/v1/inventario/calles/{a1}/finalizar", headers=op1)
    assert client.post(f"/api/v1/inventario/calles/{a1}/reabrir", headers=op1).status_code == 403
    r = client.post(f"/api/v1/inventario/calles/{a1}/reabrir", headers=sup)
    assert r.status_code == 200 and r.json()["estado"] == "en_proceso"


def test_usuarios_y_equipos(client, datos):
    adm = token(client, "admin")
    r = client.post("/api/v1/usuarios", headers=adm, json={"username": "operario3", "nombre_completo": "Operario Tres",
                                                           "rol": "operario", "password": "Cambiar123!"})
    assert r.status_code == 201
    nuevo = r.json()["id"]
    assert client.get("/api/v1/auth/me", headers=token(client, "operario3")).json()["rol"] == "operario"
    ops = client.get("/api/v1/usuarios", headers=adm, params={"rol": "operario"}).json()
    assert len(ops) == 3

    sup = token(client, "supervisor")
    eq = client.post("/api/v1/equipos", headers=sup, json={"nombre": "Equipo Azul", "miembros": [nuevo]}).json()
    assert eq["miembros"][0]["es_lider"] is True
    r = client.put(f"/api/v1/equipos/{eq['id']}/miembros", headers=sup, json=[nuevo, datos["usuarios"]["operario2"]])
    assert len(r.json()["miembros"]) == 2
    r = client.put(f"/api/v1/equipos/{eq['id']}/miembros", headers=sup, json=[datos["usuarios"]["admin"]])
    assert r.status_code == 422
