#!/bin/sh
set -eu

until mc alias set surgepilot "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"; do
  sleep 2
done

until mc ready surgepilot; do
  sleep 2
done

mc mb --ignore-existing "surgepilot/$MINIO_BUCKET"
