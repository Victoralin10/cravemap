"""Carga seed/dishes.json en la tabla. Uso: python seed/seed.py <TableName>"""
import json, sys, pathlib, boto3
from decimal import Decimal

table = boto3.resource("dynamodb").Table(sys.argv[1])
dishes = json.loads(pathlib.Path(__file__).with_name("dishes.json").read_text(), parse_float=Decimal)
with table.batch_writer() as b:
    for d in dishes:
        b.put_item(Item=d)
print(f"{len(dishes)} platos cargados en {sys.argv[1]}")
