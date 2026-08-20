"""Check minimo: python3 lambdas/test_feedback.py"""
import json, os, sys
from decimal import Decimal

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("FEEDBACK_TABLE", "dummy")
os.environ["PLATOS_IDS"] = "ceviche,lomo-saltado"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feedback
from feedback import validar

OK = {"local": "Barranco#node/123", "plato": "ceviche", "tipo": "no_existe"}


def malo(**kw):
    """Aplica un cambio sobre el payload valido y exige que lo rechace."""
    item, error = validar({**OK, **kw})
    assert item is None and error, f"deberia rechazar {kw}"
    return error


# --- el payload valido pasa y sale listo para Dynamo ---------------------------
item, error = validar(OK)
assert error is None and item["procesado"] is False and item["comentario"] == ""
assert item["ts"].startswith("20") and "#" in item["ts"], "ts = ISO8601 + sufijo unico"
assert validar(OK)[0]["ts"] != item["ts"], "dos reportes del mismo segundo no se pisan"
assert set(item) == {"local", "ts", "plato", "tipo", "comentario", "procesado"}, \
    "solo campos de la lista blanca llegan a la tabla"

# --- tipo -----------------------------------------------------------------------
for t in ("borrar", "", None, 1, ["precio"]):
    malo(tipo=t)
for t in ("no_existe", "precio", "dato", "agregar"):
    body = {**OK, "tipo": t, **({"precio_sugerido": 25.0} if t == "precio" else {})}
    assert validar(body)[1] is None, t

# --- local: {distrito}#{osm_id} --------------------------------------------------
for l in ("Barranco", "Barranco#123", "#node/1", "Barranco#node/", "Barranco#node/abc",
          "Barranco#node/1 ", " Barranco#node/1", "Barranco#node/1\nSurco#node/2",
          "Barranco#nodo/1", "", None, 42, {"local": "x"}, "B" * 41 + "#node/1"):
    malo(local=l)
for l in ("Barranco#node/123", "San Juan de Lurigancho#way/9", "Lima#relation/1"):
    assert validar({**OK, "local": l})[1] is None, l

# --- plato: tiene que existir en el catalogo -------------------------------------
malo(plato="pizza")
malo(plato=None)
malo(plato=["ceviche"])
assert validar({**OK, "plato": "lomo-saltado"})[1] is None

# --- comentario ------------------------------------------------------------------
assert validar({**OK, "comentario": "x" * 300})[1] is None
malo(comentario="x" * 301)
malo(comentario=123)
assert validar({**OK, "comentario": "  rico  "})[0]["comentario"] == "rico"

# --- precio_sugerido: solo con tipo 'precio' y en rango ---------------------------
assert "solo aplica" in malo(precio_sugerido=25.0), "no aplica a tipo no_existe"
for p in (0, 0.99, 500.1, 1000, -5, "25", True, None, [25]):
    malo(tipo="precio", precio_sugerido=p)
for p in (1, 25.5, 500):
    assert validar({**OK, "tipo": "precio", "precio_sugerido": p})[1] is None, p
assert validar({**OK, "tipo": "precio", "precio_sugerido": 25.5})[0]["precio_sugerido"] == \
    Decimal("25.5"), "va como Decimal, Dynamo no acepta float"

# --- nada fuera de la lista blanca -----------------------------------------------
malo(oculto=True)
malo(procesado=True)
malo(ts="2020-01-01")
malo(**{"": 1})
for b in (None, [], "texto", 5, {}):
    assert validar(b)[0] is None, b

# --- handler: 202 y un solo put_item ---------------------------------------------
escrito = []
feedback.table = type("T", (), {"put_item": lambda self, Item: escrito.append(Item)})()

r = feedback.handler({"body": json.dumps(OK)}, None)
assert r["statusCode"] == 202 and json.loads(r["body"]) == {"ok": True}
assert len(escrito) == 1 and escrito[0]["local"] == OK["local"]

r = feedback.handler({"body": json.dumps({**OK, "tipo": "nada"})}, None)
assert r["statusCode"] == 400 and "error" in json.loads(r["body"])
assert feedback.handler({"body": "{no json"}, None)["statusCode"] == 400
assert feedback.handler({}, None)["statusCode"] == 400, "sin body tampoco escribe"
assert len(escrito) == 1, "ningun payload rechazado toco la tabla"
print("ok")
