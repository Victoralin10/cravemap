import json, os, boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models.openai import OpenAIModel

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL = os.environ.get("MODEL_ID", "google.gemma-4-31b")
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

SYSTEM = """Eres la brujula de antojos de CraveMap, en Lima, Peru.
Recibes un antojo en lenguaje natural. Usa la herramienta buscar_platos para ver
que hay disponible; si el antojo menciona un limite de precio o un distrito, pasalos
como filtro. Elige los 3 platos que mejor calcen, del mejor al peor.
Responde SOLO los ids, uno por linea, sin numeracion ni texto extra."""

_cache = []


def _dishes():
    """Scan cacheado en el contenedor. ponytail: 40 platos caben de sobra; si crece, GSI por distrito."""
    if not _cache:
        _cache.extend(
            {**d, "precio": float(d["precio"]), "lat": float(d["lat"]), "lng": float(d["lng"])}
            for d in table.scan()["Items"]
        )
    return _cache


@tool
def buscar_platos(precio_max: float = 0, distrito: str = "") -> str:
    """Lista platos de Lima disponibles. precio_max en soles (0 = sin limite).
    distrito filtra por distrito exacto ("" = todos). Devuelve una linea por plato:
    id | nombre | S/precio | distrito | tags."""
    hits = [
        d for d in _dishes()
        if (not precio_max or d["precio"] <= precio_max)
        and (not distrito or d["distrito"].lower() == distrito.lower())
    ]
    if not hits:
        return "Sin platos para ese filtro. Vuelve a llamar sin filtros."
    return "\n".join(
        f'{d["id"]} | {d["nombre"]} | S/{d["precio"]:g} | {d["distrito"]} | {", ".join(d["tags"])}'
        for d in hits
    )


def pick_ids(text, valid, n=3):
    """Ids validos en el orden que los dio el modelo, sin repetir.
    lstrip, no strip: los ids terminan en digitos ("ceviche-01")."""
    out = []
    for line in text.splitlines():
        i = line.strip().lstrip("-*.0123456789 ")
        if i in valid and i not in out:
            out.append(i)
    return out[:n]


app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    craving = (payload or {}).get("craving", "").strip()
    if not craving:
        return {"error": "falta 'craving'"}
    if len(craving) > 300:
        return {"error": "antojo demasiado largo"}

    agent = Agent(
        model=OpenAIModel(
            bedrock_mantle_config={"region": REGION},
            model_id=MODEL,
            params={"max_completion_tokens": 512},
        ),
        system_prompt=SYSTEM,
        tools=[buscar_platos],
    )
    by_id = {d["id"]: d for d in _dishes()}
    try:
        ids = pick_ids(str(agent(f"Antojo: {craving}")), by_id)
    except Exception as e:
        print(f"agente fallo: {e}")
        ids = []
    return {"craving": craving, "dishes": [by_id[i] for i in ids] or _dishes()[:3]}


if __name__ == "__main__":
    app.run()
