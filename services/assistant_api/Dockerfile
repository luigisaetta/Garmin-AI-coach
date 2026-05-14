FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN pip install --no-cache-dir \
    cryptography \
    fastapi \
    garminconnect \
    openai \
    pydantic \
    pypdf \
    python-dotenv \
    python-multipart \
    uvicorn

COPY services ./services

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

CMD ["uvicorn", "services.assistant_api.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
