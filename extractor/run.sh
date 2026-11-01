#!/bin/sh
# Runs one extractor pass: ./run.sh format|meta|content [--kind ...] [--limit N] [--shard K/N]
# Reads the cold store read-only and decrypts into a RAM-only /work; writes to the DB as archive_app.
# Lives on the VPS at /root/archive_extractor/run.sh.
exec docker run --rm --network archive_net \
  --env-file /root/archive_app/.env --env-file /root/archive_files/.env \
  -v /srv/cold_backup:/data:ro --tmpfs /work:size=2500m \
  --cpus 3 --memory 4g archive_extractor "$@"
