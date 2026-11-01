# Rules for agents

The archive of a career: everything collected, stored by hash, read and narrowed down to what matters. Concept and regulation live in the Azure DevOps wiki of EvidenceVault; the current state is in [HANDOFF.md](HANDOFF.md).

## Working with the owner
- Concept before code: agree a short description and get a go-ahead before writing code or files.
- Entities and relations first, tables after. Don't invent terms: take them from archival and library standards (OAIS, PREMIS, IFLA LRM, Dublin Core, ISAD(G)).
- Documents are minimal: a rule is 2-3 sentences, details go to notes or an appendix.
- One step at a time, nothing in parallel unless asked. Finish what was started before opening something new.

## Data
- **Only on top.** What was added never changes. A processing adds its rows next to the earlier ones and never overwrites or deletes; versions compete, one is selected.
- Another tool, another setting, another line of code is a new method (`archive.method`), with its code zipped into `method.code`.
- One pass, one table: the meta pass writes only `meta`, the content pass only `content`. Meta is about the document (title, author, date, from/to), content is what is written in it.
- Categories are verdicts of methods (`artifact_category`); tags are our working decisions (`artifact_tag`), taken off with a date and a reason, never deleted.
- Sensitive data (identity documents, medicine, finances, family, third parties) is kept only as a reference, never as content.

## Database
- Schemas: `archive` (library), `dict` (shared dictionaries, no prefix), `career` (working extract). Every key is `bigint`.
- Names: one word is an entity, two words a link table, a reference is `<entity>_id`; `inbox` is the load table.
- Migrations are `db/NNN_*.sql`, applied in order as the admin role; code runs as `archive_app`.

## Infrastructure
- Secrets live only on the VPS (`.env` files there), never on this PC or in the repository.
- Shell scripts keep LF line endings. Long ssh sessions drop: start long jobs with `nohup … < /dev/null &` and check them with short connections.
- Board: Azure DevOps DigitIn/EvidenceVault, default Agile process, only for priorities and history. Commit messages carry `AB#<story id>`.
