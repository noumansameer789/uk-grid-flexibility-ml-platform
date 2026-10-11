FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    GRIDFLEX_DATA_DIR=/app/data GRIDFLEX_MODEL_DIR=/app/models/production
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home appuser
COPY requirements-runtime.lock ./
RUN pip install -r requirements-runtime.lock
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps .
COPY models/production/model.txt models/production/model_card.json models/production/reference.json models/production/replay.json ./models/production/
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4)"
CMD ["gridflex", "serve"]
