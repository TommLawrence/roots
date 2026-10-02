# Records inbox — where the school's files arrive

This folder is the drop point for the school's existing paper-first records,
exported or scanned exactly as they are (messy is expected).

The agent reads this folder **only through the official filesystem MCP server**
(borrowed, see `borrowed/README.md`) — never through its own file-access code.
That keeps file reads sandboxed to this directory, auditable, and out of our
server's attack surface.

## What goes here

| File type | Example | How it is used |
|---|---|---|
| Term result exports (CSV) | `sample_term_export.csv` | Rows are ingested as raw evidence events; the newest row wakes the agent |
| Scanned report cards (PDF/JPG) | `report_card_L002_y3t3.pdf` | Read via MCP for manual/LLM reference (roadmap: OCR) |
| Remark book exports (CSV/TXT) | `remarks_y3.csv` | Teacher notes ingested as `note` events |

## How it runs

```bash
python -m agent.run --from-inbox          # pick up the first pending export
```

Requires Node (npx) for the official filesystem MCP server; if Node is not
available the run falls back to a direct, clearly-labelled read-only listing so
the pipeline still works offline. Files successfully processed are renamed to
`*.done` so nothing is ingested twice.
