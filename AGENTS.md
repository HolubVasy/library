# Rules for agents

Library: the cold archive of everything collected, the hot working selection and the portfolios made from it. Concept and regulation live in the Azure DevOps wiki of the Library project; the current state is in [HANDOFF.md](HANDOFF.md).

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

## Tests
- Every PR with code carries tests for the criteria of its story; CI runs them on an empty Postgres after all migrations.
- Test data is made up and lives in `tests/seed.sql`; real archive data never goes into tests.
- A model call is replaced by a stub in tests; the quality of a model's output is checked live by the owner after the merge.
- The agent merges its own PR (squash, delete the branch) only when CI is green and the Claude review says 0 findings; otherwise it fixes and waits for the next round. The owner is called only when the work is blocked or after three rounds without a clean result.

## Infrastructure
- Secrets live only on the VPS (`.env` files there), never on this PC or in the repository. The one exception is `ANTHROPIC_API_KEY` for the PR review, kept in GitHub's encrypted Actions secrets.
- Shell scripts keep LF line endings. Long ssh sessions drop: start long jobs with `nohup … < /dev/null &` and check them with short connections.
- Board: Azure DevOps DigitIn/Library, default Agile process, only for priorities and history. Commit messages carry `AB#<story id>`.
- The agent works from the board: it reads the story and its acceptance criteria there, sets the story Active when it starts, Resolved after the merge with a one-line comment (PR link and result), and the owner closes it after the live check.
