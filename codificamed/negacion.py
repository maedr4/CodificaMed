"""Detección de contexto clínico al estilo NegEx/ConText, adaptada al español.

Marca cada token como afirmado, negado, incierto o familiar. Un disparador abre
un alcance que llega hasta el fin de la oración o hasta un término de cierre.
"""
from .preprocesamiento import Token

AFIRMADO, NEGADO, INCIERTO, FAMILIAR = "afirmado", "negado", "incierto", "familiar"

# Disparadores que preceden al hallazgo
DISPARADORES_PREVIOS = {
    NEGADO: [
        "niega", "nego", "no", "sin", "ni", "se descarta", "descarta", "descarto",
        "descartandose", "ausencia de", "negativo para", "libre de", "no presenta",
        "no refiere", "no hay", "no se observa", "no se evidencia", "sin evidencia de",
        "sin signos de",
    ],
    INCIERTO: ["sospecha de", "probable", "posible", "a descartar", "descartar", "en estudio de"],
    FAMILIAR: [
        "antecedentes familiares", "antecedente familiar", "madre", "padre", "hermano",
        "hermana", "abuelo", "abuela", "tio", "tia", "hijo", "hija",
    ],
}
# Disparadores que aparecen después del hallazgo
DISPARADORES_POSTERIORES = {NEGADO: ["descartado", "descartada", "descartados", "descartadas"]}
# Frases que contienen un disparador pero no niegan nada
PSEUDO_DISPARADORES = ["sin aura", "sin embargo", "no obstante", "sin cambios", "no solo"]
# Palabras que cierran el alcance de un disparador previo
CIERRES = {"pero", "aunque", "embargo", "salvo", "excepto", "diagnostico"}
VENTANA_POSTERIOR = 3


def _coincide(tokens: list[Token], i: int, frase: str) -> int:
    """Devuelve cuántos tokens ocupa la frase si empieza en la posición i, o 0."""
    partes = frase.split()
    if i + len(partes) > len(tokens):
        return 0
    for k, p in enumerate(partes):
        if tokens[i + k].texto != p or tokens[i + k].oracion != tokens[i].oracion:
            return 0
    return len(partes)


def detectar_contexto(tokens: list[Token]) -> list[str]:
    """Devuelve una etiqueta de contexto para cada token."""
    estados = [AFIRMADO] * len(tokens)

    # "a descartar" debe ganar frente a "descartar" negado, por eso se prueban primero las frases largas
    previos = sorted(
        ((estado, f) for estado, frases in DISPARADORES_PREVIOS.items() for f in frases),
        key=lambda x: -len(x[1].split()),
    )
    i = 0
    while i < len(tokens):
        pseudo = max((_coincide(tokens, i, f) for f in PSEUDO_DISPARADORES), default=0)
        if pseudo:
            i += pseudo
            continue
        encontrado = None
        for estado, frase in previos:
            n = _coincide(tokens, i, frase)
            if n:
                encontrado = (estado, n)
                break
        if not encontrado:
            i += 1
            continue
        estado, n = encontrado
        j = i + n
        while j < len(tokens) and tokens[j].oracion == tokens[i].oracion:
            if tokens[j].texto in CIERRES:
                break
            # Un disparador de otro tipo cierra el alcance actual
            if any(_coincide(tokens, j, f) for e, f in previos if e != estado):
                break
            estados[j] = estado
            j += 1
        i = j

    for estado, frases in DISPARADORES_POSTERIORES.items():
        for i, tok in enumerate(tokens):
            if tok.texto in frases:
                for k in range(max(0, i - VENTANA_POSTERIOR), i):
                    if tokens[k].oracion == tok.oracion:
                        estados[k] = estado
    return estados
