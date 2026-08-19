"""Proxy delgado: el navegador no puede firmar SigV4, asi que CloudFront -> este Lambda -> AgentCore."""
import json, os, urllib.parse, boto3, urllib3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = os.environ["AWS_REGION"]
ARN = os.environ["AGENT_RUNTIME_ARN"]
URL = (f"https://bedrock-agentcore.{REGION}.amazonaws.com"
       f"/runtimes/{urllib.parse.quote(ARN, safe='')}/invocations?qualifier=DEFAULT")

http = urllib3.PoolManager()
creds = boto3.Session().get_credentials()


def handler(event, context):
    craving = json.loads(event.get("body") or "{}").get("craving", "").strip()
    if not craving:
        return _json(400, {"error": "falta 'craving'"})
    if len(craving) > 300:
        return _json(400, {"error": "antojo demasiado largo"})

    body = json.dumps({"craving": craving})
    headers = {
        "content-type": "application/json",
        # el runtime exige >=33 chars; el request id de Lambda es un uuid de 36
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": context.aws_request_id,
    }
    req = AWSRequest("POST", URL, data=body, headers=headers)
    SigV4Auth(creds.get_frozen_credentials(), "bedrock-agentcore", REGION).add_auth(req)
    r = http.request("POST", URL, body=body, headers=dict(req.headers))
    if r.status != 200:
        print(f"agentcore {r.status}: {r.data[:300].decode(errors='replace')}")
        return _json(502, {"error": "la brujula no responde"})
    return _json(200, json.loads(r.data))


def _json(code, payload):
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
