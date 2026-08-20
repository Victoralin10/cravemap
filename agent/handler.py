import json

from brujula import elegir


def handler(event, _ctx):
    craving = json.loads(event.get("body") or "{}").get("craving", "").strip()
    if not craving:
        return _json(400, {"error": "falta 'craving'"})
    if len(craving) > 300:
        return _json(400, {"error": "antojo demasiado largo"})
    return _json(200, {"craving": craving, "dishes": elegir(craving)})


def _json(code, payload):
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
