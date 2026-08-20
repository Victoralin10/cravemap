"""Check minimo: python3 agent/test_agent.py"""
import os, sys, types
from decimal import Decimal

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("TABLE_NAME", "dummy")

# strands vive en el venv; para probar la logica pura basta un doble de 3 lineas.
for nombre, attrs in (
    ("strands", {"Agent": object, "tool": lambda f: f}),
    ("strands.models", {}),
    ("strands.models.openai", {"OpenAIModel": object}),
):
    sys.modules.setdefault(nombre, types.ModuleType(nombre)).__dict__.update(attrs)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent
from agent import pick_ids
from boto3.dynamodb.conditions import Key

# --- pick_ids: claves plato#local, un local por plato -------------------------
valid = {
    "ceviche#Miraflores#node/1": 1,
    "ceviche#Barranco#node/2": 1,
    "lomo-saltado#Miraflores#node/3": 1,
    "picarones#Surco#node/4": 1,
}
K = list(valid)

assert pick_ids("\n".join([K[0], K[2], K[3]]), valid) == [K[0], K[2], K[3]]
assert pick_ids(f"- {K[0]}\n2. {K[2]}", valid) == [K[0], K[2]], "limpia vinetas y numeracion"
assert pick_ids(f"{K[0]}\n{K[1]}\n{K[2]}", valid) == [K[0], K[2]], "un solo local por plato"
assert pick_ids("pizza#Lince#node/9\nno existe", valid) == [], "descarta lo inventado"
assert pick_ids("\n".join(K + ["x"]), valid) == [K[0], K[2], K[3]], "corta en 3"
assert pick_ids("", valid) == []
assert pick_ids(K[0], valid) == [K[0]], "no mutila el sufijo numerico de la clave"

# --- buscar_locales: query filtrada + precio en Python ------------------------
class TablaFalsa:
    def __init__(self, items):
        self.items, self.kw = items, None

    def query(self, **kw):
        self.kw = kw
        return {"Items": self.items}


def item(local, precio):
    return {"plato": "ceviche", "local": local, "lugar": "Punto", "distrito": local.split("#")[0],
            "precio": Decimal(str(precio)), "lat": Decimal("-12.1"), "lng": Decimal("-77.0")}


agent.table = TablaFalsa([item("Miraflores#node/1", 40), item("Barranco#node/2", 20)])
out = agent.buscar_locales("ceviche")
assert agent.table.kw["KeyConditionExpression"] == Key("plato").eq("ceviche"), "query por plato"
assert agent.table.kw["Limit"] == 60
assert out.splitlines()[0] == "Miraflores#node/1 | Punto | S/40 | Miraflores"

agent.buscar_locales("ceviche", distrito="Barranco")
assert agent.table.kw["KeyConditionExpression"] == (
    Key("plato").eq("ceviche") & Key("local").begins_with("Barranco#")
), "el distrito va como begins_with en la sort key"

out = agent.buscar_locales("ceviche", precio_max=25)
assert "KeyConditionExpression" in agent.table.kw and "FilterExpression" not in agent.table.kw, \
    "el precio NO va en la query: Dynamo aplica Limit antes del filtro"
assert out.splitlines() == ["Barranco#node/2 | Punto | S/20 | Barranco"], "filtra precio en Python"

agent.table = TablaFalsa([])
assert "Sin locales" in agent.buscar_locales("ceviche"), "avisa cuando no hay nada"

# --- lo que ven las tools se puede reconstruir para la respuesta HTTP ---------
d = agent._dish(agent._vistos["ceviche#Barranco#node/2"])
assert d["id"] == "ceviche#Barranco#node/2" and d["precio"] == 20.0 and isinstance(d["lat"], float)
print("ok")

# Los locales respaldados por OSM salen antes que los inferidos.
agent.table = TablaFalsa([
    {**item("Surco#node/9", 30), "cuisine_fuente": "inferido"},
    {**item("Lince#node/8", 30), "cuisine_fuente": "osm"},
])
assert agent.buscar_locales("ceviche").splitlines()[0].startswith("Lince#node/8"), \
    "primero lo que OSM respalda"
