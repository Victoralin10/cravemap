FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent.py .
ENV AWS_REGION=us-east-1
EXPOSE 8080
CMD ["python", "agent.py"]
