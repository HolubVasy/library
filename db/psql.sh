#!/bin/sh
# Runs psql as the app role (archive_app) inside archive_net; /root/archive_app/work is mounted at /work.
# Lives on the VPS at /root/archive_app/psql.sh; sync_cold.py calls it over ssh.
exec docker run --rm -i --network archive_net --env-file /root/archive_app/.env \
  -v /root/archive_app/work:/work pgvector/pgvector:pg17 psql -X -v ON_ERROR_STOP=1 "$@"
