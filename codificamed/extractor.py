"""Reconocimiento de entidades clínicas por diccionario.

Busca en la nota los sinónimos del catálogo CIE-10. Tolera errores de tipeo
mediante comparación aproximada y asigna a cada mención su contexto clínico.
"""
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from .catalogo import Entrada
from .negacion import AFIRMADO, detectar_contexto
from .preprocesamiento import Token, tokenizar

UMBRAL_SIMILITUD = 0.92
LONGITUD_MINIMA_APROXIMADA = 8


@dataclass
class Mencion:
    codigo: str
    texto: str
    inicio: int
    fin: int
    estado: str
    similitud: float


class ExtractorEntidades:
    def __init__(self, catalogo: dict[str, Entrada]):
        self.exactos: dict[tuple, str] = {}
        self.por_longitud: dict[int, list[tuple[str, str]]] = defaultdict(list)
        for codigo, entrada in catalogo.items():
            for sinonimo in entrada.sinonimos:
                partes = tuple(t.texto for t in tokenizar(sinonimo))
                self.exactos.setdefault(partes, codigo)
                self.por_longitud[len(partes)].append((" ".join(partes), codigo))
        self.longitud_maxima = max(self.por_longitud)

    def _buscar_aproximado(self, frase: str, n: int) -> tuple[str, float] | None:
        mejor = None
        for sinonimo, codigo in self.por_longitud.get(n, []):
            if abs(len(sinonimo) - len(frase)) > 2 or len(sinonimo) < LONGITUD_MINIMA_APROXIMADA:
                continue
            comparador = SequenceMatcher(None, frase, sinonimo)
            if comparador.quick_ratio() < UMBRAL_SIMILITUD:
                continue
            similitud = comparador.ratio()
            if similitud >= UMBRAL_SIMILITUD and (mejor is None or similitud > mejor[1]):
                mejor = (codigo, similitud)
        return mejor

    def extraer(self, texto: str, usar_contexto: bool = True) -> tuple[list[Mencion], list[Token], list[str]]:
        tokens = tokenizar(texto)
        estados = detectar_contexto(tokens) if usar_contexto else [AFIRMADO] * len(tokens)
        candidatas = []
        for n in range(self.longitud_maxima, 0, -1):
            for i in range(len(tokens) - n + 1):
                ventana = tokens[i:i + n]
                if ventana[0].oracion != ventana[-1].oracion:
                    continue
                # La ventana no puede cortar una abreviatura expandida
                if i > 0 and tokens[i - 1].inicio == ventana[0].inicio:
                    continue
                if i + n < len(tokens) and tokens[i + n].inicio == ventana[-1].inicio:
                    continue
                partes = tuple(t.texto for t in ventana)
                if partes in self.exactos:
                    candidatas.append((i, n, self.exactos[partes], 1.0))
                elif len(" ".join(partes)) >= LONGITUD_MINIMA_APROXIMADA:
                    hallazgo = self._buscar_aproximado(" ".join(partes), n)
                    if hallazgo:
                        candidatas.append((i, n, *hallazgo))

        # Se conservan las menciones más largas y, a igual longitud, las más parecidas
        candidatas.sort(key=lambda c: (-(tokens[c[0] + c[1] - 1].fin - tokens[c[0]].inicio), -c[3]))
        ocupados, menciones = set(), []
        for i, n, codigo, similitud in candidatas:
            rango = set(range(i, i + n))
            if rango & ocupados:
                continue
            ocupados |= rango
            inicio, fin = tokens[i].inicio, tokens[i + n - 1].fin
            # El contexto lo decide el primer token: un "sin" dentro del término forma parte de él
            menciones.append(Mencion(codigo, texto[inicio:fin], inicio, fin, estados[i], round(similitud, 3)))
        menciones.sort(key=lambda m: m.inicio)
        return menciones, tokens, estados
