FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git bash \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements_txt .
RUN pip install --no-cache-dir -r requirements_txt
COPY core ./core
COPY schema ./schema
COPY scripts ./scripts
COPY ui_backend ./ui_backend
COPY tests ./tests
CMD ["python", "-m", "scripts.main"]
