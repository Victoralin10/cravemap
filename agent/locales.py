import os, boto3
from boto3.dynamodb.conditions import Key
from strands import tool

from catalogo import PLATOS

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

# Locales que las tools devolvieron en ESTA invocacion: "plato#local" -> item de Dynamo.
vistos = {}


@tool
def buscar_locales(plato: str, distrito: str = "", precio_max: float = 0) -> str:
    """Busca locales de Lima que sirven un plato del catalogo.

    plato: el id exacto del catalogo (obligatorio).
    distrito: nombre exacto del distrito, "" para todos.
    precio_max: soles, 0 para sin limite.

    Devuelve hasta 8 lineas: local | lugar | S/precio | distrito.
    Usa el valor de la primera columna tal cual para armar tu respuesta final."""
    cond = Key("plato").eq(plato)
    if distrito:
        cond = cond & Key("local").begins_with(distrito + "#")
    items = table.query(KeyConditionExpression=cond, Limit=60)["Items"]
    # El precio se filtra aca, en Python, a proposito: Dynamo aplica Limit ANTES de
    # FilterExpression, asi que moverlo a la query devolveria casi nada. No lo "arregles".
    cabe = [i for i in items if not precio_max or float(i["precio"]) <= precio_max]
    # Primero los locales donde OSM dice que sirven esa cocina; los inferidos (la carta
    # generica de un restaurante sin tag cuisine) son relleno, no la primera opcion.
    hits = sorted(cabe, key=lambda i: i.get("cuisine_fuente") != "osm")[:8]
    if not hits:
        return "Sin locales para ese filtro. Vuelve a llamar sin distrito ni precio_max."
    vistos.update({f'{i["plato"]}#{i["local"]}': i for i in hits})
    return "\n".join(
        f'{i["local"]} | {i["lugar"]} | S/{float(i["precio"]):g} | {i["distrito"]}' for i in hits
    )


def dish(item):
    """Item de Dynamo -> shape que espera el front. id compuesto: unico y estable."""
    return {
        **item,
        "id": f'{item["plato"]}#{item["local"]}',
        "precio": float(item["precio"]),
        "lat": float(item["lat"]),
        "lng": float(item["lng"]),
    }


def fallback():
    """Si el agente falla: un local de cada uno de los 3 primeros platos del catalogo.
    Con PK/SK ya no hay scan barato, y devolver platos reales gana a devolver vacio."""
    out = []
    for p in PLATOS[:3]:
        out += [
            dish(i)
            for i in table.query(KeyConditionExpression=Key("plato").eq(p["id"]), Limit=1)["Items"]
        ]
    return out
