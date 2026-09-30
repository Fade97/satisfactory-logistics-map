# Logistics Map: build the frontend (Node/pnpm), then a slim Python image with the service + finished website.
FROM node:22-slim AS web
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY mapsvc ./mapsvc
COPY gamedata ./gamedata
COPY --from=web /src/frontend/dist ./frontend/dist
RUN useradd --uid 1000 --create-home map && mkdir -p /data/saves && chown -R map /data
USER map
ENV MAP_DATA=/data MAP_SAVES=/data/saves PYTHONUNBUFFERED=1 TZ=Europe/Berlin
VOLUME /data
EXPOSE 8050
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/api/status', timeout=4)"
CMD ["python", "-u", "mapd.py", "--port", "8050"]
