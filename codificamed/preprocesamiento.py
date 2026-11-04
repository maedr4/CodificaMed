"""Preprocesamiento del texto clínico.

Normaliza el texto, separa oraciones, tokeniza conservando la posición de cada
token en la nota original y expande las abreviaturas clínicas más comunes.
"""
import re
import unicodedata
from dataclasses import dataclass

ABREVIATURAS = {
    "hta": "hipertension arterial",
    "dm": "diabetes mellitus",
    "dm1": "diabetes mellitus tipo 1",
    "dm2": "diabetes mellitus tipo 2",
    "ivu": "infeccion de vias urinarias",
    "itu": "infeccion de vias urinarias",
    "epoc": "enfermedad pulmonar obstructiva cronica",
    "erc": "enfermedad renal cronica",
    "fa": "fibrilacion auricular",
    "iam": "infarto agudo de miocardio",
    "acv": "accidente cerebrovascular",
    "ait": "accidente isquemico transitorio",
    "tvp": "trombosis venosa profunda",
    "tep": "tromboembolia pulmonar",
    "erge": "enfermedad por reflujo gastroesofagico",
    "hpb": "hiperplasia prostatica benigna",
    "icc": "insuficiencia cardiaca congestiva",
    "nac": "neumonia adquirida en la comunidad",
    "gea": "gastroenteritis aguda",
    "tce": "traumatismo craneoencefalico",
    "abd": "abdominal",
    "dx": "diagnostico",
    "tto": "tratamiento",
    "rx": "radiografia",
    "eco": "ecografia",
    "tac": "tomografia",
    "emo": "examen de orina",
    "ta": "tension arterial",
    "hb": "hemoglobina",
}

PATRON_TOKEN = re.compile(r"\w+", re.UNICODE)
# Fin de oración: punto, punto y coma o salto de línea, sin cortar decimales como 38.5
PATRON_ORACION = re.compile(r"(?<!\d)\.(?!\d)|\.(?=\s)|;|\n")


@dataclass
class Token:
    texto: str        # forma normalizada (minúsculas, sin tildes, abreviatura expandida)
    inicio: int       # posición en la nota original
    fin: int
    oracion: int      # índice de la oración a la que pertenece


def quitar_tildes(texto: str) -> str:
    """Pasa a minúsculas y elimina tildes conservando la longitud del texto."""
    salida = []
    for c in texto.lower():
        base = unicodedata.normalize("NFD", c)[0]
        salida.append(base)
    return "".join(salida)


def segmentar_oraciones(texto: str) -> list[tuple[int, int]]:
    """Devuelve los límites (inicio, fin) de cada oración de la nota."""
    limites, inicio = [], 0
    for m in PATRON_ORACION.finditer(texto):
        if texto[inicio:m.start()].strip():
            limites.append((inicio, m.start()))
        inicio = m.end()
    if texto[inicio:].strip():
        limites.append((inicio, len(texto)))
    return limites


def tokenizar(texto: str, expandir: bool = True) -> list[Token]:
    """Tokeniza la nota. Cada palabra expandida conserva la posición de la abreviatura."""
    oraciones = segmentar_oraciones(texto)
    tokens = []
    for m in PATRON_TOKEN.finditer(texto):
        forma = quitar_tildes(m.group())
        n_oracion = next((i for i, (a, b) in enumerate(oraciones) if a <= m.start() < b), len(oraciones))
        partes = ABREVIATURAS[forma].split() if expandir and forma in ABREVIATURAS else [forma]
        for parte in partes:
            tokens.append(Token(parte, m.start(), m.end(), n_oracion))
    return tokens


def normalizar(texto: str) -> str:
    """Forma normalizada de un texto completo, útil para comparar y vectorizar."""
    return " ".join(t.texto for t in tokenizar(texto))
