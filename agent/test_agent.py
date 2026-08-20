"""Check minimo: python3 agent/test_agent.py"""
import os, sys, types
from decimal import Decimal

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("TABLE_NAME", "dummy")

# Lo que haria el modelo en una invocacion: recibe las tools, devuelve el texto de respuesta.
guion = [lambda tools: ""]


class AgentFalso:
    def __init__(self, **kw):
        self.kw = kw

    def __call__(self, _prompt):
        return guion[0](self.kw["tools"])


# strands vive en el venv; para probar la logica pura basta un doble de 3 lineas.
for nombre, attrs in (
    ("strands", {"Agent": AgentFalso, "tool": lambda f: f}),
    ("strands.models", {}),
    ("strands.models.openai", {"OpenAIModel": lambda **kw: kw}),
):
    sys.modules.setdefault(nombre, types.ModuleType(nombre)).__dict__.update(attrs)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brujula, locales
from brujula import pick_ids
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


locales.table = TablaFalsa([item("Miraflores#node/1", 40), item("Barranco#node/2", 20)])
out = locales.buscar_locales("ceviche")
assert locales.table.kw["KeyConditionExpression"] == Key("plato").eq("ceviche"), "query por plato"
assert locales.table.kw["Limit"] == 60
assert out.splitlines()[0] == "Miraflores#node/1 | Punto | S/40 | Miraflores"

locales.buscar_locales("ceviche", distrito="Barranco")
assert locales.table.kw["KeyConditionExpression"] == (
    Key("plato").eq("ceviche") & Key("local").begins_with("Barranco#")
), "el distrito va como begins_with en la sort key"

out = locales.buscar_locales("ceviche", precio_max=25)
assert "KeyConditionExpression" in locales.table.kw and "FilterExpression" not in locales.table.kw, \
    "el precio NO va en la query: Dynamo aplica Limit antes del filtro"
assert out.splitlines() == ["Barranco#node/2 | Punto | S/20 | Barranco"], "filtra precio en Python"

locales.table = TablaFalsa([])
assert "Sin locales" in locales.buscar_locales("ceviche"), "avisa cuando no hay nada"

# --- lo que ven las tools se puede reconstruir para la respuesta HTTP ---------
d = locales.dish(locales.vistos["ceviche#Barranco#node/2"])
assert d["id"] == "ceviche#Barranco#node/2" and d["precio"] == 20.0 and isinstance(d["lat"], float)

# Los locales respaldados por OSM salen antes que los inferidos.
locales.table = TablaFalsa([
    {**item("Surco#node/9", 30), "cuisine_fuente": "inferido"},
    {**item("Lince#node/8", 30), "cuisine_fuente": "osm"},
])
assert locales.buscar_locales("ceviche").splitlines()[0].startswith("Lince#node/8"), \
    "primero lo que OSM respalda"

# --- elegir: usa lo que la tool devolvio en ESTA invocacion, y nada mas -------
locales.table = TablaFalsa([item("Barranco#node/2", 20)])
guion[0] = lambda tools: (tools[0]("ceviche"), "ceviche#Barranco#node/2")[1]
assert [x["id"] for x in brujula.elegir("ceviche")] == ["ceviche#Barranco#node/2"]

# El modelo repite la clave pero nadie llamo la tool: no debe heredarla de la corrida anterior.
guion[0] = lambda tools: "ceviche#Barranco#node/2"
dishes = brujula.elegir("otra cosa")
assert locales.vistos == {}, "vistos se limpia al entrar a elegir"
assert len(dishes) == 3, "sin ids validos cae al fallback (3 platos del catalogo)"

guion[0] = lambda tools: 1 / 0
assert len(brujula.elegir("boom")) == 3, "si el agente revienta, fallback"
print("ok")
