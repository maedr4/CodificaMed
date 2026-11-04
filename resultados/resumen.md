| Sistema | Modelo | Precisión | Recall | F1 | F1 por categoría | Negados sugeridos | Segundos por nota | Errores |
|---|---|---|---|---|---|---|---|---|
| gemini | gemini-3.5-flash-lite | 0.965 | 1.000 | 0.982 | 0.982 | 0/22 | 3.44 | 0 |
| ollama | llama3.2:3b | 0.689 | 0.927 | 0.791 | 0.806 | 0/22 | 4.83 | 0 |
| reglas | diccionario + reglas | 0.705 | 1.000 | 0.827 | 0.840 | 0/22 | 0.0 | 0 |
| reglas (sin negación) | diccionario + reglas | 0.550 | 1.000 | 0.710 | 0.719 | 22/22 | 0.0 | 0 |
