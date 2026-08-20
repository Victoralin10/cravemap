import os
from strands import Agent
from strands.models.openai import OpenAIModel

import locales
from catalogo import CATALOGO

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL = os.environ.get("MODEL_ID", "google.gemma-4-31b")

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


def elegir(craving):
    """Antojo -> hasta 3 dishes listos para el front. Nunca lanza: cae al fallback."""
    # ponytail: dict de modulo; un contenedor atiende una request a la vez, pero el estado
    # sucio entre invocaciones es un bug real. Si eso deja de valer, pasalo por invocacion.
    locales.vistos.clear()
    agent = Agent(
        model=OpenAIModel(
            bedrock_mantle_config={"region": REGION},
            model_id=MODEL,
            params={"max_completion_tokens": 512},
        ),
        system_prompt=SYSTEM,
        tools=[locales.buscar_locales],
    )
    try:
        ids = pick_ids(str(agent(f"Antojo: {craving}")), locales.vistos)
    except Exception as e:
        print(f"agente fallo: {e}")
        ids = []
    return [locales.dish(locales.vistos[i]) for i in ids] or locales.fallback()
