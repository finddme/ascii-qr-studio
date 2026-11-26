FROM python:3.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY ascii_pipeline.py ascii_qr.py server.py test*.py VERSION ./
COPY web/ ./web/
RUN mkdir -p /app/dev && chown app:app /app/dev
LABEL org.opencontainers.image.source="https://github.com/finddme/ascii-qr-studio"
USER app
EXPOSE 8787
CMD ["python", "server.py"]
