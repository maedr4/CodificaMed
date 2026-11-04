"""Recuperación de códigos candidatos (la parte de búsqueda del enfoque RAG).

Representa cada entrada del catálogo como un vector TF-IDF de n-gramas de
caracteres. Esta representación tolera errores de tipeo y variaciones de
género y número, y no necesita descargar modelos.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .catalogo import Entrada
from .preprocesamiento import normalizar, segmentar_oraciones


class RecuperadorCIE10:
    def __init__(self, catalogo: dict[str, Entrada]):
        self.codigos = list(catalogo)
        self.vectorizador = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.matriz = self.vectorizador.fit_transform([catalogo[c].documento for c in self.codigos])

    def buscar(self, consulta: str, k: int = 5, umbral: float = 0.12) -> list[tuple[str, float]]:
        similitudes = cosine_similarity(self.vectorizador.transform([normalizar(consulta)]), self.matriz)[0]
        orden = similitudes.argsort()[::-1][:k]
        return [(self.codigos[i], float(similitudes[i])) for i in orden if similitudes[i] >= umbral]

    def buscar_en_nota(self, texto: str, k: int = 4) -> dict[str, float]:
        """Consulta el catálogo oración por oración y guarda la mejor similitud de cada código."""
        resultados: dict[str, float] = {}
        for inicio, fin in segmentar_oraciones(texto):
            for codigo, similitud in self.buscar(texto[inicio:fin], k):
                resultados[codigo] = max(similitud, resultados.get(codigo, 0.0))
        return resultados
