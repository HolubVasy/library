#!/bin/sh
# Applies every migration in order to an empty database, as the admin role. Connection comes from PG* variables.
set -e
cd "$(dirname "$0")/../db"
for f in 0*.sql; do
  psql -X -q -v ON_ERROR_STOP=1 -v app_pw=test -v reader_pw=test -f "$f" > /dev/null
  echo "applied $f"
done
