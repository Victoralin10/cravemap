FROM --platform=linux/arm64 public.ecr.aws/lambda/python:3.13
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t ${LAMBDA_TASK_ROOT}
COPY agent.py ${LAMBDA_TASK_ROOT}/
CMD ["agent.handler"]
