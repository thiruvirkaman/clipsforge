# backend/Dockerfile
# Multi-stage build: install dependencies in a builder stage, then copy
# only the installed packages + app source into a slim runtime image.

FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


FROM python:3.11-slim AS runtime

WORKDIR /app

# ffmpeg is required at runtime for the clip render pipeline; libpq5 is the
# runtime counterpart of libpq-dev needed by psycopg2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY ./app ./app
COPY alembic.ini .
COPY ./alembic ./alembic
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Pre-create /data/media owned by appuser: when the media_data named volume
# is first mounted here, Docker seeds it from this directory's existing
# content (including ownership), so the volume ends up appuser-writable
# instead of defaulting to root.
RUN mkdir -p /data/media \
    && chmod +x /docker-entrypoint.sh \
    && chown -R appuser:appuser /app /home/appuser/.local /data/media

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

# Every service using this image (api, worker) runs migrations once before
# starting its own command -- `alembic upgrade head` against an already
# up-to-date schema is a fast no-op, so this is safe for both services to
# do independently on every startup/restart.
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
