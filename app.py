"""Interfaz web de CodificaMed. Ejecutar con: streamlit run app.py"""
import html
import json
from pathlib import Path

import streamlit as st

from codificamed import Codificador
from codificamed.negacion import AFIRMADO

RAIZ = Path(__file__).resolve().parent
NOMBRES = {
    "reglas": "Solo reglas (sin modelo)",
    "ollama": "Modelo local (Ollama)",
    "claude": "API externa (Claude)",
    "openai": "API externa (OpenAI)",
    "gemini": "API externa (Gemini)",
}
# Color de fondo y de borde para cada contexto clínico
COLORES = {
    "afirmado": ("#d5f5df", "#2f9e5b"),
    "negado": ("#ffe0e0", "#d64545"),
    "incierto": ("#fff3c4", "#c99a06"),
    "familiar": ("#e8e8ef", "#6b6b80"),
}
ESTILOS = """
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.cabecera {background: linear-gradient(120deg, #0f766e, #14919b); color: #fff;
           padding: 1.4rem 1.8rem; border-radius: 14px; margin-bottom: 1.2rem;}
.cabecera h1 {color: #fff; margin: 0; font-size: 2rem;}
.cabecera p {margin: .3rem 0 0; opacity: .9;}
.nota {background: #fff; border: 1px solid #dde7e5; border-radius: 10px;
       padding: 1rem 1.2rem; line-height: 2; font-size: 1.02rem;}
.nota mark {padding: 1px 4px; border-radius: 4px; color: #111;}
.nota sub {font-size: .68rem; font-weight: 600; opacity: .75;}
.tarjeta {display: flex; gap: .9rem; align-items: flex-start; background: #fff;
          border: 1px solid #dde7e5; border-left: 5px solid #0f766e; border-radius: 10px;
          padding: .7rem 1rem; margin-bottom: .55rem;}
.tarjeta .codigo {background: #0f766e; color: #fff; font-weight: 700; border-radius: 6px;
                  padding: .2rem .55rem; font-family: monospace; font-size: 1rem; white-space: nowrap;}
.tarjeta .descripcion {font-weight: 600;}
.tarjeta .evidencia {color: #4b5b58; font-size: .9rem; font-style: italic;}
.cifras {display: flex; flex-wrap: wrap; gap: .5rem; margin: .2rem 0 .9rem;}
.cifra {background: #fff; border: 1px solid #dde7e5; border-radius: 10px; padding: .4rem .9rem;}
.cifra b {display: block; font-size: 1.4rem; color: #0f766e;}
.cifra span {font-size: .8rem; color: #4b5b58;}
.etiqueta {display: inline-block; padding: .15rem .6rem; margin: 0 .3rem .35rem 0;
           border-radius: 999px; font-size: .85rem; color: #111;}
</style>
"""

st.set_page_config(page_title="CodificaMed", page_icon="🩺", layout="wide")
st.markdown(ESTILOS, unsafe_allow_html=True)


@st.cache_resource
def obtener_codificador() -> Codificador:
    return Codificador()


@st.cache_data
def casos_de_ejemplo() -> dict[str, str]:
    lineas = (RAIZ / "datos" / "casos_prueba.jsonl").read_text(encoding="utf-8").splitlines()
    return {(c := json.loads(l))["id"]: c["texto"] for l in lineas if l.strip()}


def etiqueta(texto: str, estado: str) -> str:
    fondo, borde = COLORES[estado]
    return f'<span class="etiqueta" style="background:{fondo};border:1px solid {borde}">{html.escape(texto)}</span>'


def resaltar(nota: str, resultado) -> str:
    """Marca en la nota la evidencia de cada código y los hallazgos descartados."""
    marcas = [(s.inicio, s.fin, AFIRMADO, s.codigo) for s in resultado.sugerencias if s.inicio is not None]
    marcas += [(m.inicio, m.fin, m.estado, m.estado) for m in resultado.descartados]
    marcas.sort()
    partes, cursor = [], 0
    for inicio, fin, estado, texto in marcas:
        if inicio < cursor:
            continue
        fondo, borde = COLORES[estado]
        texto = html.escape(texto)
        partes.append(html.escape(nota[cursor:inicio]))
        partes.append(
            f'<mark style="background:{fondo};border-bottom:2px solid {borde}" title="{texto}">'
            f"{html.escape(nota[inicio:fin])}<sub> {texto}</sub></mark>"
        )
        cursor = fin
    partes.append(html.escape(nota[cursor:]))
    return '<div class="nota">' + "".join(partes).replace("\n", "<br>") + "</div>"


def tarjeta(sugerencia) -> str:
    return (
        f'<div class="tarjeta"><span class="codigo">{html.escape(sugerencia.codigo)}</span><div>'
        f'<div class="descripcion">{html.escape(sugerencia.descripcion)}</div>'
        f'<div class="evidencia">Evidencia: “{html.escape(sugerencia.evidencia)}”</div></div></div>'
    )


def cifras(valores: dict[str, object]) -> str:
    """Fila de cifras que se acomoda al ancho disponible."""
    return '<div class="cifras">' + "".join(
        f'<div class="cifra"><b>{valor}</b><span>{nombre}</span></div>' for nombre, valor in valores.items()
    ) + "</div>"


def mostrar(resultado, nota: str) -> None:
    st.caption(f"{NOMBRES[resultado.proveedor]} · {resultado.modelo}")
    if resultado.error:
        st.error(resultado.error)
        return
    st.markdown(cifras({
        "códigos sugeridos": len(resultado.sugerencias),
        "hallazgos descartados": len(resultado.descartados),
        "segundos": resultado.segundos,
    }), unsafe_allow_html=True)

    st.markdown("##### Nota con la evidencia marcada")
    st.markdown(resaltar(nota, resultado), unsafe_allow_html=True)

    st.markdown("##### Códigos CIE-10 sugeridos")
    if resultado.sugerencias:
        st.markdown("".join(tarjeta(s) for s in resultado.sugerencias), unsafe_allow_html=True)
    else:
        st.info("El sistema no encontró diagnósticos confirmados.")

    if resultado.descartados:
        st.markdown("##### Hallazgos que no se codifican")
        st.markdown(
            "".join(etiqueta(f"{m.texto} · {m.estado}", m.estado) for m in resultado.descartados),
            unsafe_allow_html=True,
        )
    if resultado.rechazados:
        with st.expander(f"Sugerencias del modelo rechazadas por la validación ({len(resultado.rechazados)})"):
            st.table([{"Código": c, "Motivo": m} for c, m in resultado.rechazados])
    if resultado.candidatos:
        with st.expander(f"Candidatos recuperados del catálogo ({len(resultado.candidatos)})"):
            st.write(", ".join(resultado.candidatos))
    if resultado.respuesta_modelo:
        with st.expander("Respuesta original del modelo"):
            st.code(resultado.respuesta_modelo, language="json")


def comparar_resultados(local, externo) -> None:
    """Resume en qué códigos coinciden los dos modelos."""
    a, b = set(local.codigos), set(externo.codigos)
    with st.container(border=True):
        st.markdown("##### Comparación entre los dos modelos")
        st.markdown(cifras({
            "códigos en los que coinciden": len(a & b),
            "solo el modelo local": len(a - b),
            "solo la API externa": len(b - a),
        }), unsafe_allow_html=True)
        for titulo, codigos in [("Coinciden", a & b), ("Solo local", a - b), ("Solo API", b - a)]:
            if codigos:
                st.markdown(f"**{titulo}:** {', '.join(sorted(codigos))}")


def pestana_codificar(codificador: Codificador, proveedor: str, comparar: bool, externo: str, ejemplo: str) -> None:
    with st.container(border=True):
        nota = st.text_area(
            "Nota clínica (solo datos ficticios)",
            value=casos_de_ejemplo().get(ejemplo, ""),
            height=150,
            placeholder="Ejemplo: Paciente de 58 años con HTA y DM2. Niega dolor torácico.",
        )
        pulsado = st.button("Codificar", type="primary", icon="🔎", disabled=not nota.strip())
    if not pulsado:
        st.caption("Escriba una nota o elija un caso de ejemplo en la barra lateral y pulse Codificar.")
        return

    if comparar:
        with st.spinner("Consultando el modelo local..."):
            local = codificador.codificar(nota, "ollama")
        with st.spinner("Consultando la API externa..."):
            remoto = codificador.codificar(nota, externo)
        if not local.error and not remoto.error:
            comparar_resultados(local, remoto)
        izquierda, derecha = st.columns(2, gap="large")
        with izquierda:
            st.subheader("Modelo local")
            mostrar(local, nota)
        with derecha:
            st.subheader("API externa")
            mostrar(remoto, nota)
    else:
        with st.spinner("Codificando..."):
            mostrar(codificador.codificar(nota, proveedor), nota)


def pestana_resultados() -> None:
    filas, casos = [], 0
    for ruta in sorted((RAIZ / "resultados").glob("*.json")):
        d = json.loads(ruta.read_text(encoding="utf-8"))
        casos = d["casos"]
        c = d["codigo_completo"]
        filas.append({
            "Sistema": NOMBRES[d["proveedor"]] + ("" if d["negacion"] else ", sin negación"),
            "Modelo": d["modelo"],
            "Precisión": c["precision"],
            "Recall": c["recall"],
            "F1": c["f1"],
            "Negados sugeridos": f"{d['errores_negacion']} de {d['hallazgos_negados']}",
            "Segundos por nota": d["segundos_promedio"],
        })
    if not filas:
        st.info("Aún no hay resultados. Ejecute: python evaluar.py --proveedor reglas ollama gemini")
        return
    filas.sort(key=lambda f: -f["F1"])
    st.markdown(f"Resultados de `evaluar.py` sobre {casos} casos ficticios con códigos conocidos.")
    st.dataframe(
        filas,
        hide_index=True,
        width="stretch",
        column_config={
            "Precisión": st.column_config.NumberColumn(format="%.3f"),
            "Recall": st.column_config.NumberColumn(format="%.3f"),
            "F1": st.column_config.ProgressColumn("F1", min_value=0, max_value=1, format="%.3f"),
        },
    )
    st.caption(
        "Precisión: de los códigos sugeridos, cuántos eran correctos. "
        "Recall: de los códigos correctos, cuántos encontró. F1: promedio armónico de ambos."
    )


def pestana_como_funciona() -> None:
    pasos = [
        ("1. Preparar el texto", "Pasa la nota a minúsculas, quita tildes, separa oraciones y expande abreviaturas como HTA o DM2."),
        ("2. Detectar la negación", "Marca cada palabra como afirmada, negada, dudosa o de un familiar según frases como «niega» o «madre con»."),
        ("3. Buscar candidatos", "Compara la nota con el catálogo CIE-10 y arma una lista corta de códigos posibles."),
        ("4. Elegir y validar", "El modelo elige los códigos y copia la frase que los justifica. El sistema descarta los que no tienen evidencia real o están negados."),
    ]
    columnas = st.columns(2) + st.columns(2)
    for columna, (titulo, texto) in zip(columnas, pasos):
        with columna.container(border=True, height="stretch"):
            st.markdown(f"**{titulo}**")
            st.write(texto)
    imagen = RAIZ / "informe" / "arquitectura.png"
    if imagen.exists():
        st.image(str(imagen), caption="Arquitectura de CodificaMed")


codificador = obtener_codificador()
st.markdown(
    '<div class="cabecera"><h1>🩺 CodificaMed</h1>'
    "<p>Sugerencia de códigos CIE-10 a partir de notas clínicas, con la evidencia de cada código.</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Configuración")
    proveedores = list(NOMBRES)
    proveedor = st.selectbox(
        "Motor de codificación", proveedores, index=proveedores.index(codificador.cfg.proveedor),
        format_func=NOMBRES.get,
    )
    comparar = st.toggle("Comparar modelo local y API externa")
    externo = st.selectbox("API para comparar", ["gemini", "claude", "openai"], format_func=NOMBRES.get, disabled=not comparar)
    st.divider()
    ejemplo = st.selectbox("Cargar caso de ejemplo", ["(ninguno)"] + list(casos_de_ejemplo()))
    st.divider()
    st.markdown("**Colores de la nota**")
    st.markdown("".join(etiqueta(estado, estado) for estado in COLORES), unsafe_allow_html=True)
    st.caption("Todos los casos son ficticios. El sistema sugiere códigos; la decisión final es del codificador.")

codificar, resultados, como_funciona = st.tabs(["Codificar nota", "Resultados de la evaluación", "Cómo funciona"])
with codificar:
    pestana_codificar(codificador, proveedor, comparar, externo, ejemplo)
with resultados:
    pestana_resultados()
with como_funciona:
    pestana_como_funciona()
