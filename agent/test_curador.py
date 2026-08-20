"""Check minimo del curador nocturno: python3 agent/test_curador.py"""
import os, sys, types
from decimal import Decimal

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("TABLE_NAME", "dummy")
os.environ.setdefault("FEEDBACK_TABLE", "dummy-feedback")

# Lo que responde el modelo en una invocacion.
guion = [lambda prompt: "nada"]


class AgentFalso:
    def __init__(self, **kw):
        self.kw = kw

    def __call__(self, prompt):
        return guion[0](prompt)


# strands vive en el venv; para probar la logica pura basta un doble de 3 lineas.
for nombre, attrs in (
    ("strands", {"Agent": AgentFalso, "tool": lambda f: f}),
    ("strands.models", {}),
    ("strands.models.openai", {"OpenAIModel": lambda **kw: kw}),
):
    sys.modules.setdefault(nombre, types.ModuleType(nombre)).__dict__.update(attrs)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curador, locales
from curador import UMBRAL, aprobar, propuestas

L = "Barranco#node/123"
n = [0]


def fb(plato, tipo, **kw):
    n[0] += 1
    return {"local": L, "ts": f"2026-08-20T08:00:0{n[0]}Z#ab", "plato": plato, "tipo": tipo,
            "comentario": "", "procesado": False, **kw}


# --- consenso: el conteo manda, no el modelo -----------------------------------
assert UMBRAL == 2
uno = [fb("ceviche", "no_existe")]
dos = [fb("ceviche", "no_existe"), fb("ceviche", "no_existe")]

assert aprobar([("ocultar", "ceviche")], uno) == [], "un reporte aislado no basta"
assert aprobar([("ocultar", "ceviche")], dos) == [("ocultar", "ceviche")], "dos coincidentes si"
assert aprobar([("ocultar", "ceviche")], []) == [], "el modelo no puede inventar acciones"
assert aprobar([("ocultar", "lomo-saltado")], dos) == [], "el consenso es por plato"
assert aprobar([("agregar", "ceviche")], dos) == [], "los votos son por accion, no por plato"
assert aprobar([], dos) == [], "si el modelo no propone nada, no se toca nada"

# Contradictorios: unos dicen que no esta y otro dice que si. Nadie gana.
mixto = dos + [fb("ceviche", "agregar")]
assert aprobar([("ocultar", "ceviche")], mixto) == [], "reportes contradictorios se descartan"
assert aprobar([("agregar", "ceviche")], mixto + [fb("ceviche", "agregar")]) == [], \
    "aunque el 'agregar' llegue al umbral, el 'ocultar' lo contradice"

# 'dato' es texto libre para que lo lea el modelo: no vota.
assert aprobar([("ocultar", "ceviche")], uno + [fb("ceviche", "dato")]) == []

precios = [fb("ceviche", "precio", precio_sugerido=Decimal("30")),
           fb("ceviche", "precio", precio_sugerido=Decimal("32"))]
assert aprobar([("precio", "ceviche")], precios) == [("precio", "ceviche")]

# --- propuestas: parsea al modelo y descarta lo demas ---------------------------
assert propuestas("ocultar|ceviche\nprecio | ceviche") == [("ocultar", "ceviche"), ("precio", "ceviche")]
assert propuestas("- ocultar|ceviche\n2. agregar|tacu-tacu") == [("ocultar", "ceviche"), ("agregar", "tacu-tacu")]
assert propuestas("nada") == [] and propuestas("") == []
assert propuestas("borrar|ceviche\nHe decidido que...") == [], "solo acciones conocidas"
assert propuestas("ocultar|ceviche\nocultar|ceviche") == [("ocultar", "ceviche")], "sin repetidos"

# --- aplicar: ocultar marca, no borra; el precio sale de la mediana -------------
class TablaFalsa:
    def __init__(self, items=()):
        self.items, self.calls = list(items), []

    def update_item(self, **kw):
        self.calls.append(("update", kw))

    def put_item(self, **kw):
        self.calls.append(("put", kw))

    def scan(self, **kw):
        self.calls.append(("scan", kw))
        return {"Items": self.items}

    def delete_item(self, **kw):
        raise AssertionError("el curador nunca borra")


locales.table = TablaFalsa()
curador.feedback = TablaFalsa()

curador.aplicar(L, "ocultar", "ceviche", dos)
tipo, kw = locales.table.calls[-1]
assert tipo == "update" and kw["UpdateExpression"] == "SET oculto = :t", "ocultar es un flag"
assert kw["ExpressionAttributeValues"][":t"] is True and kw["Key"] == {"plato": "ceviche", "local": L}
assert "ConditionExpression" in kw, "no crea el par si no existia"

curador.aplicar(L, "precio", "ceviche", precios + [fb("lomo-saltado", "precio", precio_sugerido=Decimal("99"))])
kw = locales.table.calls[-1][1]
assert kw["ExpressionAttributeValues"][":p"] == Decimal("31"), "mediana de lo reportado, por plato"
assert isinstance(kw["ExpressionAttributeValues"][":p"], Decimal), "Dynamo no acepta float"

base = {"plato": "otro", "local": L, "lugar": "Punto", "distrito": "Barranco",
        "precio": Decimal("20"), "lat": Decimal("-12.1"), "lng": Decimal("-77.0"), "oculto": True}
locales.table = TablaFalsa([base])
curador.aplicar(L, "agregar", "ceviche", dos)
item = locales.table.calls[-1][1]["Item"]
assert locales.table.calls[0][0] == "scan", "los datos del local salen de un par que ya existe"
assert item["plato"] == "ceviche" and item["local"] == L and item["lugar"] == "Punto"
assert item["nombre"] == "Ceviche" and item["cuisine_fuente"] == "feedback"
assert "oculto" not in item, "no hereda el flag del par que sirvio de molde"

# --- curar: aplica lo aprobado y marca TODO el feedback del local --------------
locales.table, curador.feedback = TablaFalsa(), TablaFalsa()
guion[0] = lambda prompt: "ocultar|ceviche"
items = dos + [fb("lomo-saltado", "no_existe")]
assert curador.curar(L, items) == 1, "solo el plato con consenso"
assert len(locales.table.calls) == 1
assert len(curador.feedback.calls) == len(items), "todo el feedback del local queda procesado"
assert curador.feedback.calls[0][1]["ExpressionAttributeValues"] == {":t": True}

# El modelo ve el resumen con el conteo ya hecho.
texto = curador.resumen(L, items)
assert "ocultar|ceviche = 2 reporte(s)" in texto and L in texto

# Si el modelo alucina, el filtro de consenso lo para antes de tocar la tabla.
locales.table, curador.feedback = TablaFalsa(), TablaFalsa()
guion[0] = lambda prompt: "ocultar|lomo-saltado\nagregar|ceviche\nborrar todo"
assert curador.curar(L, dos) == 0 and locales.table.calls == []
assert len(curador.feedback.calls) == 2, "sin acciones, igual se marca como procesado"
print("ok")
