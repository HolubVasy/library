#!/bin/sh
# Runs the CV reading pass: ./run.sh --model claude-sonnet-5-5 --price-in USD --price-out USD
# Writes to the DB as archive_app; the API key comes from the same .env. Lives on the VPS at /root/archive_cv_reader/run.sh.
# archive_net is internal (the DB, no internet); archive_egress reaches the API.
exec docker run --rm --network archive_net --network archive_egress --env-file /root/archive_app/.env \
  --cpus 1 --memory 512m archive_cv_reader "$@"
