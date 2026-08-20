import json, pathlib

# Catalogo de platos: viaja en el zip del Lambda, no en Dynamo. Se lee una vez por contenedor.
PLATOS = json.loads(pathlib.Path(__file__).with_name("platos.json").read_text())

# Aplanado para el system prompt: id | nombre | tipo | tags.
CATALOGO = "\n".join(
    f'{p["id"]} | {p["nombre"]} | {p["tipo"]} | {", ".join(p["tags"])}' for p in PLATOS
)
