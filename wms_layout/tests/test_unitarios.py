from decimal import Decimal

from app.services.normalizacion import normalizar_cabecera, normalizar_paquete
from app.services.ocr_service import parsear_texto_etiqueta


def test_normalizar_paquete():
    assert normalizar_paquete(" pkg 001 ") == "PKG001"
    assert normalizar_paquete("123456.0") == "123456"
    assert normalizar_paquete("000777") == "000777"
    assert normalizar_paquete(None) == ""


def test_normalizar_cabecera():
    assert normalizar_cabecera("Nº Paquete") == "no_paquete"  # NFKD: º -> o (alias contemplado)
    assert normalizar_cabecera("Descripción ") == "descripcion"
    assert normalizar_cabecera("U.M.") == "u_m"


def test_parseo_etiqueta_ocr():
    texto = """ALSINA S.A.
    Artículo: ART-0045
    Nº Paquete: pkg-778899
    Cantidad: 24,5 M
    """
    d = parsear_texto_etiqueta(texto)
    assert d["numero_de_paquete"] == "PKG-778899"
    assert d["articulo"] == "ART-0045"
    assert d["cantidad"] == Decimal("24.5")
    assert d["unidad_de_medida"] == "M"
