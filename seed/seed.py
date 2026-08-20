"""Carga seed/locales.json en la tabla. Uso: python3 seed/seed.py <NombreTabla>

build_dishes.py escribe un objeto JSON por linea, asi que esto lo carga en
streaming: con decenas de miles de pares no tiene sentido meterlos todos en RAM.
"""
import json, sys, pathlib, boto3
from decimal import Decimal

table = boto3.resource("dynamodb").Table(sys.argv[1])
n = 0
with pathlib.Path(__file__).with_name("locales.json").open() as f, table.batch_writer() as b:
    for linea in f:
        linea = linea.strip().rstrip(",").strip("[]")
        if not linea:
            continue
        b.put_item(Item=json.loads(linea, parse_float=Decimal))
        n += 1
        if n % 2000 == 0:
            print(f"{n} pares...", flush=True)
print(f"{n} pares plato-local cargados en {sys.argv[1]}")
