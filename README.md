# CodificaMed

Prototipo que sugiere códigos CIE-10 a partir de una nota clínica en texto libre y muestra la frase que justifica cada código. Distingue diagnósticos confirmados de hallazgos negados, descartados, dudosos o de familiares.

Proyecto de la materia Base de Conocimiento, unidad de Procesamiento de Lenguaje Natural (ESPOCH, FIE, EIS).

## Requisitos

- Python 3.10 o superior
- [Ollama](https://ollama.com) para el modelo local
- Una clave de API externa para el modelo externo: Google Gemini (clave gratuita en [Google AI Studio](https://aistudio.google.com)), Anthropic (Claude) u OpenAI

## Instalación

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
```

En Linux o macOS:

```bash
source .venv/bin/activate
```

Luego:

```bash
pip install -r requirements.txt
```

```bash
ollama pull llama3.2:3b
```

Copie `.env.example` como `.env` y complete la clave de la API externa. El archivo `.env` no se sube al repositorio.

## Ejecución de la interfaz

```bash
streamlit run app.py
```

La aplicación abre en `http://localhost:8501`. En la barra lateral se elige el motor de codificación:

| Motor | Qué hace |
|---|---|
| Solo reglas | Diccionario del catálogo y detección de negación, sin modelo de lenguaje |
| Modelo local (Ollama) | Pipeline completo con el modelo configurado en `OLLAMA_MODELO` |
| API externa (Gemini, Claude u OpenAI) | Pipeline completo con el modelo de la API |

El interruptor "Comparar modelo local y API externa" ejecuta la misma nota con los dos motores, muestra los resultados lado a lado y cuenta en qué códigos coinciden. La pestaña "Resultados de la evaluación" muestra las métricas guardadas en `resultados/` y la pestaña "Cómo funciona" resume los pasos del sistema. El tema de colores está en `.streamlit/config.toml`.

La carpeta `informe/` contiene el informe ejecutivo y una guía que explica qué hace cada archivo del código.

El motor por defecto se cambia en `.env` con `PROVEEDOR_LLM=reglas|ollama|gemini|claude|openai`.

## Evaluación

```bash
python evaluar.py --proveedor reglas ollama gemini
```

```bash
python evaluar.py --proveedor reglas --sin-negacion
```

Cada ejecución guarda el detalle por caso en `resultados/<proveedor>.json` y actualiza la tabla `resultados/resumen.md` con precisión, recall, F1, F1 por categoría de tres caracteres, hallazgos negados que el sistema sugirió por error y tiempo promedio por nota.

## Datos

- `datos/cie10_catalogo.csv` contiene 148 códigos CIE-10 frecuentes en consulta y hospitalización, con su descripción y sinónimos clínicos.
- `datos/casos_prueba.jsonl` contiene 36 casos clínicos ficticios con sus códigos correctos y los códigos de hallazgos negados o familiares. No hay datos reales de pacientes.

Para usar el corpus público CodiEsp (CLEF eHealth 2020), descárguelo desde Zenodo, descomprímalo en `datos/codiesp/` y conviértalo:

```bash
python scripts/convertir_codiesp.py --particion datos/codiesp/dev --salida datos/codiesp_dev.jsonl --codigos datos/codiesp/codiesp-D_codes.tsv --limite 50
```

```bash
python evaluar.py --proveedor ollama --casos datos/codiesp_dev.jsonl
```

## Estructura

```
codificamed/
  preprocesamiento.py  normalización, oraciones, tokens y abreviaturas
  negacion.py          contexto clínico (negado, incierto, familiar)
  extractor.py         reconocimiento de entidades por diccionario con tolerancia a errores de tipeo
  recuperador.py       búsqueda vectorial TF-IDF sobre el catálogo CIE-10
  llm.py               clientes de Ollama, Gemini, Claude y OpenAI
  codificador.py       orquestación del pipeline y validación de la respuesta
app.py                 interfaz Streamlit
evaluar.py             cálculo de métricas
scripts/convertir_codiesp.py
datos/                 catálogo y casos de prueba
resultados/            métricas generadas
```
