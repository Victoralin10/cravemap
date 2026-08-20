FROM --platform=linux/arm64 public.ecr.aws/lambda/python:3.13
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t ${LAMBDA_TASK_ROOT}
# platos.json es copia de seed/platos.json: el build context es agent/, no alcanza a seed/.
# Refrescala con: cp seed/platos.json agent/platos.json  (antes de cdk deploy)
COPY agent.py platos.json ${LAMBDA_TASK_ROOT}/
CMD ["agent.handler"]
