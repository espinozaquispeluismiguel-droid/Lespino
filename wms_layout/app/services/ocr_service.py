"""Extracción de campos de una foto de etiqueta (método 'foto_ia').

Estrategia: OpenCV preprocesa (gris, umbral adaptativo, enderezado básico) ->
Tesseract extrae texto -> expresiones regulares localizan los campos.
El resultado es una PROPUESTA: el operario la confirma en pantalla y luego se
llama a /inventario/registrar con metodo_ingreso='foto_ia'.

Para etiquetas complejas puede sustituirse `_extraer_texto` por una API de visión
(Google Vision, AWS Textract, Azure, o un LLM multimodal) sin tocar el resto.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.core.config import settings
from app.schemas.inventario import DatosOCR
from app.services.normalizacion import normalizar_paquete


class OCRNoDisponible(RuntimeError):
    pass


PATRONES = {
    "numero_de_paquete": [
        r"(?:N[ºo°.]?\s*(?:DE\s*)?PAQ(?:UETE)?|PAQUETE|PACKAGE|PKG|BULTO|LOTE)\s*[:#\-]?\s*([A-Z0-9\-_/]{4,40})",
    ],
    "articulo": [
        r"(?:ART(?:[IÍ]CULO)?|REF(?:ERENCIA)?|SKU|C[OÓ]D(?:IGO)?)\s*[:#\-.]?\s*([A-Z0-9\-_/.]{2,40})",
    ],
    "cantidad": [
        r"(?:CANT(?:IDAD)?|QTY|UNIDADES|UDS)\s*[:#\-.]?\s*(\d+(?:[.,]\d+)?)",
    ],
    "unidad_de_medida": [
        r"(?:U\.?M\.?|UNIDAD(?:\s*DE\s*MEDIDA)?|UOM)\s*[:#\-.]?\s*([A-Z]{1,6})\b",
        r"\d+(?:[.,]\d+)?\s*(UND|UDS|KG|M2|M3|ML|M|L|CJ|PZA|PZ)\b",
    ],
}


def _preprocesar(imagen: bytes):
    import cv2
    import numpy as np

    arr = np.frombuffer(imagen, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Imagen no válida")
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Escala: Tesseract rinde mejor con texto de ~30 px de alto
    h = gris.shape[0]
    if h < 1000:
        f = 1000 / h
        gris = cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    gris = cv2.bilateralFilter(gris, 9, 75, 75)
    return cv2.adaptiveThreshold(gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)


def _extraer_texto(imagen: bytes) -> tuple[str, float]:
    try:
        import pytesseract
    except ImportError as exc:
        raise OCRNoDisponible("Instale pytesseract, opencv-python-headless y el binario tesseract-ocr") from exc

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    proc = _preprocesar(imagen)
    data = pytesseract.image_to_data(
        proc, lang=settings.OCR_IDIOMA, config="--psm 6", output_type=pytesseract.Output.DICT
    )
    palabras = [(w, float(c)) for w, c in zip(data["text"], data["conf"]) if w.strip() and float(c) >= 0]
    texto = pytesseract.image_to_string(proc, lang=settings.OCR_IDIOMA, config="--psm 6")
    confianza = sum(c for _, c in palabras) / len(palabras) if palabras else 0.0
    return texto, round(confianza, 2)


def parsear_texto_etiqueta(texto: str) -> dict:
    t = texto.upper()
    out: dict = {}
    for campo, patrones in PATRONES.items():
        for p in patrones:
            m = re.search(p, t)
            if m:
                out[campo] = m.group(1).strip()
                break
    if "numero_de_paquete" in out:
        out["numero_de_paquete"] = normalizar_paquete(out["numero_de_paquete"])
    if "cantidad" in out:
        try:
            out["cantidad"] = Decimal(out["cantidad"].replace(",", "."))
        except InvalidOperation:
            out.pop("cantidad")
    return out


def analizar_etiqueta(imagen: bytes) -> DatosOCR:
    texto, confianza = _extraer_texto(imagen)
    campos = parsear_texto_etiqueta(texto)
    return DatosOCR(**campos, confianza=confianza, texto_crudo=texto[:2000])
