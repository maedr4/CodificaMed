"""Carga del catálogo CIE-10 usado como base de conocimiento."""
import csv
from dataclasses import dataclass, field
from pathlib import Path

from .preprocesamiento import normalizar

RUTA_CATALOGO = Path(__file__).resolve().parent.parent / "datos" / "cie10_catalogo.csv"


@dataclass
class Entrada:
    codigo: str
    descripcion: str
    sinonimos: list[str] = field(default_factory=list)

    @property
    def documento(self) -> str:
        """Texto que se vectoriza para la búsqueda semántica."""
        return normalizar(self.descripcion + " " + " ".join(self.sinonimos))


def cargar_catalogo(ruta: Path = RUTA_CATALOGO) -> dict[str, Entrada]:
    with open(ruta, encoding="utf-8") as f:
        filas = csv.DictReader(f, delimiter=";")
        return {
            fila["codigo"]: Entrada(
                fila["codigo"],
                fila["descripcion"],
                [s.strip() for s in fila["sinonimos"].split("|") if s.strip()],
            )
            for fila in filas
        }
