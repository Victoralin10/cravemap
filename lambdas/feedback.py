"""POST /api/feedback: un usuario reporta algo de un par plato-local.

Lambda ligera, sin Strands: solo boto3 (ya viene en el runtime) y stdlib. Guarda y
responde 202; quien decide que hacer con esto es el curador nocturno (agent/curador.py).
"""
import json, os, re, secrets, boto3
from datetime import datetime, timezone
from decimal import Decimal

TIPOS = ("no_existe", "precio", "dato", "agregar")
CAMPOS = ("local", "plato", "tipo", "comentario", "precio_sugerido")
# Los ids del catalogo llegan por env desde el CDK: evita una tercera copia de platos.json.
PLATOS = set(filter(None, os.environ.get("PLATOS_IDS", "").split(",")))
# "{distrito}#{osm_id}", con los distritos de Lima tal como los escribe el seed (sin tildes).
LOCAL = re.compile(r"[A-Za-z]{1,25}(?: [A-Za-z]{1,25}){0,5}#(?:node|way|relation)/[0-9]{1,12}\Z")

table = boto3.resource("dynamodb").Table(os.environ["FEEDBACK_TABLE"])


def validar(body):
    """Payload crudo -> (item para Dynamo, None) o (None, motivo del rechazo).

    Endpoint publico de escritura y sin auth: esto es el limite de confianza. Lista
    blanca de campos y tipos exactos; nada que no este aca llega a la tabla.
    """
    if not isinstance(body, dict):
        return None, "el cuerpo debe ser un objeto JSON"
    extra = set(body) - set(CAMPOS)
    if extra:
        return None, f"campo desconocido: {sorted(extra)[0]}"

    tipo = body.get("tipo")
    if tipo not in TIPOS:
        return None, f"'tipo' debe ser uno de {list(TIPOS)}"

    local = body.get("local")
    if not isinstance(local, str) or not LOCAL.match(local):
        return None, "'local' debe tener formato {distrito}#{osm_id}"

    plato = body.get("plato")
    if not isinstance(plato, str) or plato not in PLATOS:
        return None, "'plato' no existe en el catalogo"

    comentario = body.get("comentario", "")
    if not isinstance(comentario, str):
        return None, "'comentario' debe ser texto"
    if len(comentario) > 300:
        return None, "'comentario' pasa los 300 caracteres"

    item = {
        "local": local,
        "ts": f'{datetime.now(timezone.utc).isoformat(timespec="seconds")}#{secrets.token_hex(2)}',
        "plato": plato,
        "tipo": tipo,
        "comentario": comentario.strip(),
        "procesado": False,
    }

    precio = body.get("precio_sugerido")
    if tipo != "precio":
        if precio is not None:
            return None, "'precio_sugerido' solo aplica a tipo 'precio'"
        return item, None
    # isinstance(True, int) es True en Python: los bool se rechazan a mano.
    if isinstance(precio, bool) or not isinstance(precio, (int, float)):
        return None, "'precio_sugerido' debe ser un numero"
    if not 1 <= precio <= 500:
        return None, "'precio_sugerido' fuera de rango (1..500 soles)"
    item["precio_sugerido"] = Decimal(str(round(float(precio), 2)))
    return item, None


def handler(event, _ctx):
    try:
        body = json.loads(event.get("body") or "null")
    except ValueError:
        return _json(400, {"error": "JSON invalido"})
    item, error = validar(body)
    if error:
        return _json(400, {"error": error})
    table.put_item(Item=item)
    return _json(202, {"ok": True})


def _json(code, payload):
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
