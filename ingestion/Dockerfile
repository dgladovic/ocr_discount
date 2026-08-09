# Built with context = repo root (see docker-compose.yml), so it can COPY
# the shared ingestion/, db/, normalize.py, load_to_db.py used by both this
# worker and any one-off manual runs.
FROM python:3.11-slim

# Force Python to stream print() statements directly to Docker logs instantly
ENV PYTHONUNBUFFERED=1
# Tell Python that /app is the root directory for modules
ENV PYTHONPATH="/app"

# 1. poppler-utils is required by pdf2image to rasterize flyer PDFs.
# 2. chromium and chromium-driver are required by Selenium for the dynamic flyer downloaders.
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion/ ./ingestion/
COPY db/ ./db/
COPY ingestion/normalize.py ingestion/load_to_db.py ./
COPY ingestion/scheduler_entry.py ./ingestion/scheduler_entry.py

# downloads/, extracted_json/, cropped_images/ are mounted volumes -- see docker-compose.yml
RUN mkdir -p downloads extracted_json cropped_images

# Run using the -m flag so Python correctly resolves 'from ingestion.xyz import ...'
CMD ["python", "-m", "ingestion.scheduler_entry"]