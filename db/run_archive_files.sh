#!/bin/sh
# (Re)creates the archive_files container: rclone serves the encrypted store /srv/cold_backup over sftp,
# decrypting and encrypting on the fly with the keys from .env. Reachable only from the VPS itself (ssh tunnel).
# Lives on the VPS at /root/archive_files/run.sh.
# archive_net is internal (no published ports), so the port is published on the default bridge
# and archive_net is attached afterwards.
docker rm -f archive_files 2>/dev/null
docker run -d --name archive_files --restart unless-stopped \
  --env-file /root/archive_files/.env -v /srv/cold_backup:/data -p 127.0.0.1:2022:2022 \
  rclone/rclone:1.68.2 serve sftp cold: --vfs-cache-mode writes
docker network connect archive_net archive_files
