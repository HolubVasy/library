#!/bin/sh
# Runs the annotation pass: ./run.sh --model claude-haiku-5-5 --price-in USD --price-out USD [--size 50]
# Writes to the DB as archive_app; the API key comes from the same .env. Lives on the VPS at /root/archive_annotator/run.sh.
exec docker run --rm --network archive_net --env-file /root/archive_app/.env \
  --cpus 1 --memory 512m archive_annotator "$@"
