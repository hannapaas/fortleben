#!/bin/sh
# Start the site. Under Litestream when a bucket is configured, so the database on the volume is
# streamed to object storage as it changes; plain otherwise. Railway gives the port in $PORT.
set -e
cmd="uv run keikaku serve --host 0.0.0.0 --port ${PORT:-8000}"
if [ -n "$LITESTREAM_BUCKET" ]; then
  exec litestream replicate -config litestream.yml -exec "$cmd"
fi
exec $cmd
