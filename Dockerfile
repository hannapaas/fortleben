# The site on Railway (docs/ARCHITECTURE.md, "Hosting"): one service, built from this file on push.
# Set KEIKAKU_DATA_DIR to the volume's mount path and the keys as Railway variables (.env.example).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Litestream streams the database to object storage when LITESTREAM_BUCKET is set (litestream.yml).
ADD https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.tar.gz /tmp/litestream.tar.gz
RUN tar -C /usr/local/bin -xzf /tmp/litestream.tar.gz litestream && rm /tmp/litestream.tar.gz

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "bin/serve.sh"]
