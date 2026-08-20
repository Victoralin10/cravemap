"""Curador nocturno: lee el feedback acumulado y corrige la carta.

Corre una vez al dia (EventBridge, 3am Lima). Reusa el mismo zip que el agente de
antojos: mismo asset, distinto handler. El modelo propone acciones a partir del
resumen de un local; el conteo de reportes decide cuales se aplican de verdad.
"""
import os, statistics, boto3
from collections import defaultdict
from decimal import Decimal
from boto3.dynamodb.conditions import Attr
from strands import Agent
from strands.models.openai import OpenAIModel

import locales
from brujula import MODEL, REGION
from catalogo import PLATOS

# ponytail: 2 reportes coincidentes es un umbral arbitrario de demo. En serio esto se
# ponderaria por reputacion del usuario (y hoy ni siquiera hay usuarios: el endpoint es
# anonimo, asi que una misma persona puede votar dos veces). Con auth: peso por cuenta.
UMBRAL = 2

ACCION = {"no_existe": "ocultar", "precio": "precio", "agregar": "agregar"}
OPUESTA = {"ocultar": "agregar", "agregar": "ocultar"}

feedback = boto3.resource("dynamodb").Table(os.environ["FEEDBACK_TABLE"])

SYSTEM = f"""Eres el curador de datos de CraveMap, en Lima, Peru.

Recibes el feedback que dejaron los usuarios sobre UN restaurante. Decide que acciones
merecen aplicarse a la carta, por consenso: varios usuarios que coinciden en lo mismo
valen; un reporte aislado o un comentario contradictorio, no.

Acciones: ocultar (el plato no esta en la carta), precio (el precio esta mal), agregar
(el local si sirve ese plato y falta). El precio nuevo no lo eliges tu: sale de lo que
reportaron los usuarios.

Responde SOLO una linea por accion aprobada, con el formato accion|plato, usando el id
de plato tal cual aparece en el resumen. Si nada tiene consenso, responde: nada"""


def pendientes():
    """Feedback con procesado=false, agrupado por local.

    ponytail: scan con filtro, que a esta escala (un demo, feedback de una noche) es lo
    barato. Cuando la tabla crezca: GSI por 'procesado' y query en vez de scan.
    """
    grupos, kw = defaultdict(list), {"FilterExpression": Attr("procesado").eq(False)}
    while True:
        r = feedback.scan(**kw)
        for i in r["Items"]:
            grupos[i["local"]].append(i)
        if "LastEvaluatedKey" not in r:
            return grupos
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def votos(items):
    """Cuantos reportes respaldan cada (accion, plato). Los de tipo 'dato' no votan:
    son texto libre, van en el resumen para que el modelo los lea."""
    c = defaultdict(int)
    for i in items:
        if i["tipo"] in ACCION:
            c[(ACCION[i["tipo"]], i["plato"])] += 1
    return c


def resumen(local, items):
    v = votos(items)
    lineas = [f"Local: {local}", "Reportes:"]
    for i in items:
        extra = f' precio_sugerido=S/{float(i["precio_sugerido"]):g}' if "precio_sugerido" in i else ""
        com = f' "{i["comentario"]}"' if i.get("comentario") else ""
        lineas.append(f'- {i["plato"]} | {i["tipo"]}{extra}{com}')
    lineas.append("Conteo por accion:")
    lineas += [f"- {a}|{p} = {n} reporte(s)" for (a, p), n in sorted(v.items())]
    return "\n".join(lineas)


def propuestas(texto):
    """Texto del modelo -> [(accion, plato)]. Ignora todo lo que no calce."""
    out = []
    for linea in str(texto).splitlines():
        partes = [x.strip() for x in linea.strip().lstrip("-*.0123456789 ").split("|")]
        if len(partes) >= 2 and partes[0] in ACCION.values() and (partes[0], partes[1]) not in out:
            out.append((partes[0], partes[1]))
    return out


def aprobar(props, items):
    """Filtro duro sobre lo que propuso el modelo: el conteo manda.

    Un modelo alucinado (o convencido por un comentario elocuente de una sola persona)
    no puede tocar la carta si los reportes no lo respaldan. Y ocultar/agregar el mismo
    plato a la vez es contradiccion: se descartan los dos.
    """
    v = votos(items)
    return [
        (a, p)
        for a, p in props
        if v[(a, p)] >= UMBRAL and not v[(OPUESTA.get(a, ""), p)]
    ]


def aplicar(local, accion, plato, items):
    """Aplica una accion aprobada sobre la tabla de locales. Devuelve el log."""
    clave = {"plato": plato, "local": local}
    if accion == "precio":
        # El precio lo pone la mediana de lo reportado, no el modelo: un outlier no manda.
        nuevo = statistics.median(
            float(i["precio_sugerido"]) for i in items
            if i["plato"] == plato and "precio_sugerido" in i
        )
        locales.table.update_item(
            Key=clave,
            UpdateExpression="SET precio = :p, precio_estimado = :f",
            ExpressionAttributeValues={":p": _dec(nuevo), ":f": False},
            ConditionExpression=Attr("plato").exists(),
        )
        return f"precio {plato}@{local} -> S/{nuevo:g}"
    if accion == "ocultar":
        # No borra: marca. Un consenso equivocado se deshace cambiando un flag; un
        # delete_item no se deshace, y el par plato-local se perderia para siempre.
        locales.table.update_item(
            Key=clave,
            UpdateExpression="SET oculto = :t",
            ExpressionAttributeValues={":t": True},
            ConditionExpression=Attr("plato").exists(),
        )
        return f"oculto {plato}@{local}"
    base = _base(local)
    if not base:
        return f"agregar {plato}@{local} omitido: no hay datos del local"
    p = next(x for x in PLATOS if x["id"] == plato)
    locales.table.put_item(
        Item={**base, **clave, "nombre": p["nombre"], "tags": p["tags"],
              "precio_estimado": True, "cuisine_fuente": "feedback"}
    )
    return f"agregado {plato}@{local}"


def _base(local):
    """Datos del local (lugar, distrito, lat, lng, precio) tomados de un par que ya existe.

    ponytail: scan filtrado por la sort key. Se paga solo cuando un 'agregar' pasa el
    consenso, que es raro y de madrugada. Si dejara de serlo: GSI por 'local'.
    """
    kw = {"FilterExpression": Attr("local").eq(local), "Limit": 500}
    while True:
        r = locales.table.scan(**kw)
        if r["Items"]:
            return {k: v for k, v in r["Items"][0].items() if k != "oculto"}
        if "LastEvaluatedKey" not in r:
            return None
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _dec(x):
    return Decimal(str(round(float(x), 2)))


def curar(local, items):
    """Un local: resumen -> modelo -> filtro de consenso -> aplicar -> marcar procesado."""
    agent = Agent(
        model=OpenAIModel(
            bedrock_mantle_config={"region": REGION},
            model_id=MODEL,
            params={"max_completion_tokens": 256},
        ),
        system_prompt=SYSTEM,
    )
    acciones = aprobar(propuestas(agent(resumen(local, items))), items)
    for accion, plato in acciones:
        try:
            print(f"curador: {aplicar(local, accion, plato, items)}")
        except Exception as e:
            print(f"curador: {accion} {plato}@{local} fallo: {e}")
    # Marcar al final del local, no al principio: si esto revienta a mitad de la noche,
    # la proxima corrida reprocesa el local entero y las acciones son idempotentes.
    for i in items:
        feedback.update_item(
            Key={"local": i["local"], "ts": i["ts"]},
            UpdateExpression="SET procesado = :t",
            ExpressionAttributeValues={":t": True},
        )
    return len(acciones)


def handler(_event=None, _ctx=None):
    grupos = pendientes()
    total = 0
    for local, items in grupos.items():
        try:
            total += curar(local, items)
        except Exception as e:
            print(f"curador: local {local} fallo: {e}")
    print(f"curador: {len(grupos)} locales revisados, {total} acciones aplicadas")
    return {"locales": len(grupos), "acciones": total}
