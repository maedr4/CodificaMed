"""Orquesta el pipeline completo de codificación CIE-10.

Modo "reglas": usa solo el diccionario y la detección de negación.
Modo LLM (ollama, claude, openai, gemini): recupera candidatos del catálogo y pide al
modelo que elija los códigos y copie la frase que los justifica (RAG).
"""
import json
import re
import time
from dataclasses import dataclass, field

from .catalogo import Entrada, cargar_catalogo
from .config import Config
from .extractor import ExtractorEntidades, Mencion
from .llm import ErrorLLM, generar
from .negacion import AFIRMADO
from .preprocesamiento import quitar_tildes
from .recuperador import RecuperadorCIE10

SISTEMA = (
    "Eres un codificador clínico experto en la clasificación CIE-10. "
    "Analizas notas clínicas en español y respondes únicamente con JSON válido."
)

PLANTILLA = """NOTA CLÍNICA:
\"\"\"{nota}\"\"\"

HALLAZGOS NEGADOS, DESCARTADOS, DUDOSOS O DE FAMILIARES (no se codifican):
{descartados}

CÓDIGOS CANDIDATOS DEL CATÁLOGO CIE-10:
{candidatos}

INSTRUCCIONES:
1. Lee la nota oración por oración. Una nota suele tener varios diagnósticos y debes devolver todos los confirmados del paciente.
2. Incluye las enfermedades crónicas que figuran como antecedentes personales.
3. No codifiques hallazgos negados, descartados, dudosos ni enfermedades de familiares.
4. No codifiques un síntoma si ya está explicado por un diagnóstico que sí codificas.
5. Usa solo códigos de la lista de candidatos y prefiere el más específico.
6. En "evidencia" copia las palabras exactas de la NOTA CLÍNICA, nunca la descripción del catálogo.

Ejemplo para la nota "Antecedente de HTA. Dx: gastritis. Niega fiebre.":
{{"codigos": [{{"codigo": "I10", "evidencia": "HTA"}}, {{"codigo": "K29.7", "evidencia": "gastritis"}}]}}"""


@dataclass
class Sugerencia:
    codigo: str
    descripcion: str
    evidencia: str
    inicio: int | None
    fin: int | None
    fuente: str


@dataclass
class Resultado:
    proveedor: str
    modelo: str
    sugerencias: list[Sugerencia] = field(default_factory=list)
    descartados: list[Mencion] = field(default_factory=list)
    menciones: list[Mencion] = field(default_factory=list)
    candidatos: list[str] = field(default_factory=list)
    rechazados: list[tuple[str, str]] = field(default_factory=list)
    segundos: float = 0.0
    respuesta_modelo: str = ""
    error: str = ""

    @property
    def codigos(self) -> list[str]:
        return [s.codigo for s in self.sugerencias]


class Codificador:
    def __init__(self, cfg: Config | None = None, catalogo: dict[str, Entrada] | None = None):
        self.cfg = cfg or Config()
        self.catalogo = catalogo or cargar_catalogo()
        self.extractor = ExtractorEntidades(self.catalogo)
        self.recuperador = RecuperadorCIE10(self.catalogo)

    def codificar(self, nota: str, proveedor: str | None = None, usar_negacion: bool = True) -> Resultado:
        proveedor = proveedor or self.cfg.proveedor
        inicio = time.perf_counter()
        resultado = Resultado(proveedor, self.cfg.modelo(proveedor))
        menciones, tokens, estados = self.extractor.extraer(nota, usar_contexto=usar_negacion)
        resultado.menciones = menciones
        resultado.descartados = [m for m in menciones if m.estado != AFIRMADO]

        if proveedor == "reglas":
            self._por_reglas(resultado)
        else:
            try:
                self._por_llm(nota, proveedor, resultado, tokens, estados)
            except ErrorLLM as e:
                resultado.error = str(e)
        resultado.segundos = round(time.perf_counter() - inicio, 2)
        return resultado

    def _por_reglas(self, resultado: Resultado) -> None:
        vistos = set()
        for m in resultado.menciones:
            if m.estado == AFIRMADO and m.codigo not in vistos:
                vistos.add(m.codigo)
                resultado.sugerencias.append(
                    Sugerencia(m.codigo, self.catalogo[m.codigo].descripcion, m.texto, m.inicio, m.fin, "diccionario")
                )

    def _candidatos(self, nota: str, menciones: list[Mencion]) -> list[str]:
        candidatos = list(dict.fromkeys(m.codigo for m in menciones if m.estado == AFIRMADO))
        recuperados = self.recuperador.buscar_en_nota(nota, k=self.cfg.top_k)
        for codigo, _ in sorted(recuperados.items(), key=lambda x: -x[1]):
            if codigo not in candidatos:
                candidatos.append(codigo)
        return candidatos[: self.cfg.max_candidatos]

    def _por_llm(self, nota, proveedor, resultado: Resultado, tokens, estados) -> None:
        resultado.candidatos = self._candidatos(nota, resultado.menciones)
        descartados = "\n".join(f'- "{m.texto}" ({m.estado})' for m in resultado.descartados) or "- ninguno"
        candidatos = "\n".join(f"{c} - {self.catalogo[c].descripcion}" for c in resultado.candidatos)
        prompt = PLANTILLA.format(nota=nota, descartados=descartados, candidatos=candidatos)

        resultado.respuesta_modelo = generar(proveedor, self.cfg, SISTEMA, prompt)
        vistos = set()
        for item in _leer_json(resultado.respuesta_modelo):
            codigo = str(item.get("codigo", "")).strip().upper()
            evidencia = str(item.get("evidencia", "")).strip()
            if codigo not in self.catalogo:
                resultado.rechazados.append((codigo, "no existe en el catálogo"))
                continue
            if codigo in vistos:
                continue
            afirmadas = [m for m in resultado.menciones if m.codigo == codigo and m.estado == AFIRMADO]
            inicio, fin = _ubicar(nota, evidencia)
            if inicio is None and afirmadas:
                inicio, fin, evidencia = afirmadas[0].inicio, afirmadas[0].fin, afirmadas[0].texto
            # Validación posterior: todo código necesita una frase real de la nota que no esté negada
            if inicio is None:
                resultado.rechazados.append((codigo, "la evidencia no aparece en la nota"))
                continue
            if not afirmadas:
                en_rango = [estados[k] for k, t in enumerate(tokens) if inicio <= t.inicio < fin]
                if any(e != AFIRMADO for e in en_rango):
                    resultado.rechazados.append((codigo, "la evidencia está negada o es de un familiar"))
                    continue
            vistos.add(codigo)
            resultado.sugerencias.append(
                Sugerencia(codigo, self.catalogo[codigo].descripcion, evidencia, inicio, fin, proveedor)
            )


def _leer_json(texto: str) -> list[dict]:
    """Acepta {"codigos": [...]} o directamente la lista, con o sin texto alrededor."""
    coincidencia = re.search(r"[\[{].*[\]}]", texto, re.DOTALL)
    if not coincidencia:
        return []
    try:
        datos = json.loads(coincidencia.group())
    except json.JSONDecodeError:
        return []
    items = datos.get("codigos", []) if isinstance(datos, dict) else datos
    return [i for i in items if isinstance(i, dict)]


def _ubicar(nota: str, evidencia: str) -> tuple[int | None, int | None]:
    """Busca la evidencia en la nota sin distinguir mayúsculas ni tildes."""
    evidencia = evidencia.strip(" \"'.")
    if len(evidencia) < 2:
        return None, None
    posicion = quitar_tildes(nota).find(quitar_tildes(evidencia))
    if posicion < 0:
        return None, None
    return posicion, posicion + len(evidencia)
