FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ROOTA_PARSER=keyword

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Cache the local embedding model in the image so manual search works offline.
RUN python -m app.retrieval.prefetch

# Sessions, the docs registry and the Chroma index live here (a named volume
# in docker-compose.yml). Manuals are mounted at /docs/manuals, so the ingest
# command uses the same ../docs/manuals/<file>.pdf path as a local checkout.
RUN mkdir -p /app/data /docs/manuals
VOLUME ["/app/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
