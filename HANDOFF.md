# Handoff

State on 2026-11-01. Update when a story closes.

## Where things are
| What | Where |
|---|---|
| Cold archive (originals) | `C:\Work\Search\CV\Cold` on the owner's PC |
| Encrypted store | VPS `jobsearch-vps`, `/srv/cold_backup/objects/<aa>/<sha256>`, served by the `archive_files` container (rclone crypt) |
| Database | VPS, container `archive_db` (Postgres 17), reached by ssh tunnel; `/root/archive_app/psql.sh` runs psql as `archive_app` |
| Extractor | VPS `/root/archive_extractor`: `./run.sh format|meta|content|rtf [--kind …]`, `./after.sh` for the whole chain |
| Code | this repository; on the VPS copies are deployed by `scp` |
| Docs | Azure DevOps wiki of EvidenceVault (concept, regulation) |
| Board | dev.azure.com/DigitIn/EvidenceVault |

## Numbers
34 378 artifacts; format 34 377, meta 34 339, content 30 450 (the rest are images waiting for OCR). 9 335 letters tagged `skip` (noise and job platforms); in work 9 822 letters and 7 004 documents.

## Next, in board order
1. Try annotation on 50 documents (238): table `annotation`, 50 documents without `skip`, owner reviews.
2. Annotate everything in work (239), then mark what is career related (240), then career records (241).
3. Search by text (236), keep meta and content apart (237).

## Known debts
- Letter headers are written by the content pass; JSON/XML file content leaked into `meta` through exiftool (story 237).
- The RTF emoji fix did not create a new method; from now on the code version goes into the method.
- No database backup yet (story 235, low priority by the owner's decision).

## Pitfalls
- `pkill -f <name>` over ssh kills its own shell when the command line contains the name: match with `[s]h …`.
- Outlook letters are ANSI `.msg` from a Polish Windows: plain fields are cp1250, Cyrillic survives only in HTML, transport headers and RTF.
- `on conflict do nothing` still takes a number from an id sequence.
