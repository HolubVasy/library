# buro

A personal archive seen through the lens of a career. Everything is collected without judging it, kept encrypted on a VPS by hash, read, and then narrowed down step by step to what matters for the career.

The rules behind the code are in [docs/](docs/Картотека_доказательств_концепция.md).

## Layout
- `db/` — migrations (`NNN_*.sql`, applied in order as the admin role), sync of the cold archive, search, noise rules.
- `extractor/` — the container on the VPS that reads artifacts: format, meta, content.
- `upload_cold.ps1`, `setup_cold_crypt.ps1` — entry points on the PC.

## Commands
```
python -I db/sync_cold.py [--dry-run]      # new files in Cold → DB and the encrypted store, then a full check
python -I db/unpack_cold.py [--dry-run]    # unpack archives next to themselves, then sync
python -I db/find_file.py <words> [--get N]
```
On the VPS, in `/root/archive_extractor`: `./run.sh format|meta|content|rtf [--kind …]`, or `./after.sh` for the whole chain.

## Database
Postgres, three schemas: `archive` (the library), `dict` (dictionaries), `career` (the working extract). Nothing is overwritten: every processing adds its rows next to the earlier ones, signed with its method.
