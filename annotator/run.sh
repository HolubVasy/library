#!/bin/sh
# Runs the annotation pass: ./run.sh --model claude-haiku-5-5 --price-in USD --price-out USD [--size 50]
# Writes to the DB as archive_app; the API key comes from the same .env. Lives on the VPS at /root/archive_annotator/run.sh.
# archive_net is internal (the DB, no internet); archive_egress (docker network create archive_egress) reaches the API.
exec docker run --rm --network archive_net --network archive_egress --env-file /root/archive_app/.env \
  --cpus 1 --memory 512m archive_annotator "$@"
