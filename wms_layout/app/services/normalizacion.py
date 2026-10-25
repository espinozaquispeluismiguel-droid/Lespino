"""Normalización compartida entre la carga Excel, el escaneo QR y el OCR.

Es CRÍTICO que el número de paquete se normalice igual al cargarlo que al
escanearlo; si no, el cruce contra el maestro falla por espacios o mayúsculas.
"""
import re
import unicodedata

_ESPACIOS = re.compile(r"\s+")


def normalizar_paquete(valor: object) -> str:
    if valor is None:
        return ""
    s = str(valor).strip()
    # Excel convierte códigos numéricos en float: "123456.0" -> "123456"
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    s = _ESPACIOS.sub("", s)
    return s.upper()


def normalizar_cabecera(col: object) -> str:
    s = unicodedata.normalize("NFKD", str(col)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip().lower())
    return s.strip("_")
