"""Convierte una partición del corpus CodiEsp al formato de casos de CodificaMed.

CodiEsp (CLEF eHealth 2020) se descarga desde Zenodo. Cada partición trae una
carpeta text_files con los casos y un archivo *D.tsv con los códigos de
diagnóstico (id del caso y código separados por tabulador).

Uso:
    python scripts/convertir_codiesp.py --particion datos/codiesp/dev --salida datos/codiesp_dev.jsonl
    python scripts/convertir_codiesp.py ... --codigos datos/codiesp/codiesp-D_codes.tsv

Con --codigos se agregan al catálogo las descripciones de los códigos que aún
no tiene, para que el recuperador pueda proponerlos.
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

CATALOGO = Path(__file__).resolve().parent.parent / "datos" / "cie10_catalogo.csv"
# Letra, dos dígitos y, opcionalmente, punto con hasta cuatro caracteres (I10, E11.9, S72.001A)
FORMATO_CIE10 = re.compile(r"^[A-Z]\d{2}(\.[A-Z0-9]{1,4})?$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--particion", required=True, help="carpeta train, dev o test de CodiEsp")
    parser.add_argument("--salida", required=True)
    parser.add_argument("--codigos", help="archivo TSV de CodiEsp con código y descripción en español")
    parser.add_argument("--limite", type=int, default=0)
    args = parser.parse_args()

    particion = Path(args.particion)
    anotaciones = defaultdict(set)
    for archivo in particion.glob("*D.tsv"):
        for fila in csv.reader(open(archivo, encoding="utf-8"), delimiter="\t"):
            if len(fila) >= 2:
                anotaciones[fila[0].strip()].add(fila[1].strip().upper())

    textos = sorted((particion / "text_files").glob("*.txt"))
    if args.limite:
        textos = textos[: args.limite]
    with open(args.salida, "w", encoding="utf-8") as salida:
        for ruta in textos:
            caso = {"id": ruta.stem, "texto": ruta.read_text(encoding="utf-8"), "codigos": sorted(anotaciones[ruta.stem]), "negados": []}
            salida.write(json.dumps(caso, ensure_ascii=False) + "\n")
    print(f"{len(textos)} casos escritos en {args.salida}")

    if args.codigos:
        existentes = {f["codigo"] for f in csv.DictReader(open(CATALOGO, encoding="utf-8"), delimiter=";")}
        nuevos, ignorados = 0, 0
        with open(CATALOGO, "a", encoding="utf-8") as catalogo:
            for fila in csv.reader(open(args.codigos, encoding="utf-8"), delimiter="\t"):
                if len(fila) < 2:
                    continue
                codigo = fila[0].strip().upper()
                # Solo entran códigos con formato CIE-10, para no meter texto arbitrario en la interfaz
                if not FORMATO_CIE10.match(codigo):
                    ignorados += 1
                    continue
                if codigo not in existentes:
                    catalogo.write(f"{codigo};{fila[1].strip().replace(';', ',')};\n")
                    existentes.add(codigo)
                    nuevos += 1
        print(f"{nuevos} códigos agregados al catálogo, {ignorados} ignorados por formato inválido")


if __name__ == "__main__":
    main()
