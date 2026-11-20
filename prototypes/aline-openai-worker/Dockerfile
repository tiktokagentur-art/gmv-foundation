FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY worker.py /app/worker.py
COPY examples /app/examples
USER 65532:65532

# Safe default: synthetic offline demo; zero OpenAI requests and no external tools.
CMD ["python", "worker.py", "--input", "examples/synthetic.json", "--offline-demo"]
