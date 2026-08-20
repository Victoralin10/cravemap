import json, os, pathlib, boto3
from boto3.dynamodb.conditions import Key
from strands import Agent, tool
from strands.models.openai import OpenAIModel

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL = os.environ.get("MODEL_ID", "google.gemma-4-31b")
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

# Catalogo de platos: viaja en la imagen, no en Dynamo. Se lee una vez por contenedor.
PLATOS = json.loads(pathlib.Path(__file__).with_name("platos.json").read_text())
CATALOGO = "\n".join(
    f'{p["id"]} | {p["nombre"]} | {p["tipo"]} | {", ".join(p["tags"])}' for p in PLATOS
)

SYSTEM = f"""Eres la brujula de antojos de CraveMap, en Lima, Peru.

Catalogo de platos (id | nombre | tipo | tags):
{CATALOGO}

Flujo, en dos pasos:
1. Del antojo, elige 3 platos DISTINTOS del catalogo, del que mejor calza al que menos.
2. Para cada plato llama buscar_locales con su id. Si el antojo menciona un distrito o un
   limite de precio, pasalos como filtro; si no hay resultados, vuelve a llamar sin filtros.
   Elige un solo local por plato.

Responde SOLO 3 lineas, una por plato, con el formato plato#local: el id del plato del
catalogo y el valor exacto de la columna local que devolvio la herramienta.
Sin numeracion ni texto extra. Ejemplo: ceviche#Miraflores#node/959586057"""

# Locales que las tools devolvieron en ESTA invocacion: "plato#local" -> item de Dynamo.
_vistos = {}


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
    _vistos.update({f'{i["plato"]}#{i["local"]}': i for i in hits})
    return "\n".join(
        f'{i["local"]} | {i["lugar"]} | S/{float(i["precio"]):g} | {i["distrito"]}' for i in hits
    )


def pick_ids(text, valid, n=3):
    """Claves 'plato#local' validas en el orden que las dio el modelo, un local por plato.
    lstrip, no strip: las claves pueden terminar en digitos ("...#node/959586057")."""
    out, platos = [], set()
    for line in text.splitlines():
        k = line.strip().lstrip("-*.0123456789 ")
        if k in valid and k.split("#")[0] not in platos:
            out.append(k)
            platos.add(k.split("#")[0])
    return out[:n]


def _dish(item):
    """Item de Dynamo -> shape que espera el front. id compuesto: unico y estable."""
    return {
        **item,
        "id": f'{item["plato"]}#{item["local"]}',
        "precio": float(item["precio"]),
        "lat": float(item["lat"]),
        "lng": float(item["lng"]),
    }


def _fallback():
    """Si el agente falla: un local de cada uno de los 3 primeros platos del catalogo.
    Con PK/SK ya no hay scan barato, y devolver platos reales gana a devolver vacio."""
    out = []
    for p in PLATOS[:3]:
        out += [
            _dish(i)
            for i in table.query(KeyConditionExpression=Key("plato").eq(p["id"]), Limit=1)["Items"]
        ]
    return out


def handler(event, _ctx):
    craving = json.loads(event.get("body") or "{}").get("craving", "").strip()
    if not craving:
        return _json(400, {"error": "falta 'craving'"})
    if len(craving) > 300:
        return _json(400, {"error": "antojo demasiado largo"})

    # ponytail: dict de modulo; un contenedor atiende una request a la vez, pero el estado
    # sucio entre invocaciones es un bug real. Si eso deja de valer, pasalo por invocacion.
    _vistos.clear()
    agent = Agent(
        model=OpenAIModel(
            bedrock_mantle_config={"region": REGION},
            model_id=MODEL,
            params={"max_completion_tokens": 512},
        ),
        system_prompt=SYSTEM,
        tools=[buscar_locales],
    )
    try:
        ids = pick_ids(str(agent(f"Antojo: {craving}")), _vistos)
    except Exception as e:
        print(f"agente fallo: {e}")
        ids = []
    return _json(200, {"craving": craving, "dishes": [_dish(_vistos[i]) for i in ids] or _fallback()})


def _json(code, payload):
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
