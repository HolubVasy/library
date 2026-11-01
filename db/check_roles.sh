#!/bin/sh
# Checks the app role from inside archive_net: it can read and add, but not delete or change schema.
docker run --rm --network archive_net --env-file /root/archive_app/.env pgvector/pgvector:pg17 sh -c '
psql -At -c "select count(*) from item" 2>&1 | sed "s/^/read: /"
psql -At -c "delete from item where false" 2>&1 | sed "s/^/delete: /"
psql -At -c "create table probe(x int)" 2>&1 | sed "s/^/create: /"
'
echo "--- from the default network (other containers) archive_db is not reachable:"
docker run --rm pgvector/pgvector:pg17 sh -c 'pg_isready -h archive_db -t 3 2>&1' | sed 's/^/default net: /'
