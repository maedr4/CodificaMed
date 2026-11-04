"""Evalúa CodificaMed sobre casos con códigos conocidos.

Ejemplos:
    python evaluar.py --proveedor reglas
    python evaluar.py --proveedor reglas --sin-negacion
    python evaluar.py --proveedor ollama gemini
"""
import argparse
import json
from pathlib import Path

from codificamed import Codificador

RAIZ = Path(__file__).resolve().parent
CARPETA_RESULTADOS = RAIZ / "resultados"


def metricas(vp: int, fp: int, fn: int) -> dict:
    precision = vp / (vp + fp) if vp + fp else 0.0
    recall = vp / (vp + fn) if vp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def evaluar(codificador: Codificador, casos: list[dict], proveedor: str, usar_negacion: bool) -> dict:
    total = {"vp": 0, "fp": 0, "fn": 0}
    categoria = {"vp": 0, "fp": 0, "fn": 0}
    errores_negacion, negados_total, segundos, fallos, detalle = 0, 0, 0.0, 0, []

    for n, caso in enumerate(casos, 1):
        r = codificador.codificar(caso["texto"], proveedor, usar_negacion=usar_negacion)
        real, predicho = set(caso["codigos"]), set(r.codigos)
        total["vp"] += len(real & predicho)
        total["fp"] += len(predicho - real)
        total["fn"] += len(real - predicho)

        real_cat, pred_cat = {c[:3] for c in real}, {c[:3] for c in predicho}
        categoria["vp"] += len(real_cat & pred_cat)
        categoria["fp"] += len(pred_cat - real_cat)
        categoria["fn"] += len(real_cat - pred_cat)

        negados = set(caso.get("negados", []))
        negados_total += len(negados)
        errores_negacion += len(negados & predicho)
        segundos += r.segundos
        fallos += bool(r.error)
        detalle.append({
            "id": caso["id"],
            "esperados": sorted(real),
            "sugeridos": [{"codigo": s.codigo, "evidencia": s.evidencia} for s in r.sugerencias],
            "faltantes": sorted(real - predicho),
            "sobrantes": sorted(predicho - real),
            "negados_sugeridos": sorted(negados & predicho),
            "rechazados_por_validacion": [{"codigo": c, "motivo": m} for c, m in r.rechazados],
            "segundos": r.segundos,
            "error": r.error,
        })
        print(f"[{n:02d}/{len(casos)}] {caso['id']}  esperados={sorted(real)}  sugeridos={sorted(predicho)}  {r.segundos}s"
              + (f"  ERROR: {r.error}" if r.error else ""))

    return {
        "proveedor": proveedor,
        "modelo": codificador.cfg.modelo(proveedor),
        "negacion": usar_negacion,
        "casos": len(casos),
        "codigo_completo": {**metricas(**total), **total},
        "categoria_3_caracteres": metricas(**categoria),
        "errores_negacion": errores_negacion,
        "hallazgos_negados": negados_total,
        "segundos_promedio": round(segundos / len(casos), 2),
        "casos_con_error": fallos,
        "detalle": detalle,
    }


def escribir_resumen() -> None:
    filas = []
    for ruta in sorted(CARPETA_RESULTADOS.glob("*.json")):
        d = json.loads(ruta.read_text(encoding="utf-8"))
        c = d["codigo_completo"]
        nombre = d["proveedor"] + ("" if d["negacion"] else " (sin negación)")
        filas.append(
            f"| {nombre} | {d['modelo']} | {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} | "
            f"{d['categoria_3_caracteres']['f1']:.3f} | {d['errores_negacion']}/{d['hallazgos_negados']} | "
            f"{d['segundos_promedio']} | {d['casos_con_error']} |"
        )
    encabezado = (
        "| Sistema | Modelo | Precisión | Recall | F1 | F1 por categoría | Negados sugeridos | Segundos por nota | Errores |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    (CARPETA_RESULTADOS / "resumen.md").write_text(encabezado + "\n" + "\n".join(filas) + "\n", encoding="utf-8")
    print("\n" + encabezado + "\n" + "\n".join(filas))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--proveedor", nargs="+", default=["reglas"], choices=["reglas", "ollama", "claude", "openai", "gemini"])
    parser.add_argument("--sin-negacion", action="store_true", help="desactiva la detección de negación")
    parser.add_argument("--casos", default=str(RAIZ / "datos" / "casos_prueba.jsonl"))
    parser.add_argument("--limite", type=int, default=0, help="evalúa solo los primeros N casos")
    args = parser.parse_args()

    casos = [json.loads(l) for l in Path(args.casos).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limite:
        casos = casos[: args.limite]
    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    codificador = Codificador()
    for proveedor in args.proveedor:
        print(f"\n=== {proveedor} ({codificador.cfg.modelo(proveedor)}) ===")
        resultado = evaluar(codificador, casos, proveedor, not args.sin_negacion)
        sufijo = "_sin_negacion" if args.sin_negacion else ""
        ruta = CARPETA_RESULTADOS / f"{proveedor}{sufijo}.json"
        ruta.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        c = resultado["codigo_completo"]
        print(f"Precisión {c['precision']}  Recall {c['recall']}  F1 {c['f1']}")
    escribir_resumen()


if __name__ == "__main__":
    main()
