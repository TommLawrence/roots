# The MCP servers we did NOT write

Two official reference servers, borrowed for exactly one reason each:

## 1. `sqlite` — generic reads over raw history

**Server:** official reference `sqlite` MCP server
(`uvx mcp-server-sqlite --db-path data/longview.db`, or the Node equivalent
`@modelcontextprotocol/server-sqlite`).

**Why borrow instead of build (the one line the submission form asks for):**
generic read-only SQL over the records database is a solved, audited problem -
the official server gives the agent ad-hoc query power over the raw history
without us adding a hand-rolled query tool (and its edge cases) to our own
server's attack surface.

## 2. `filesystem` — sandboxed reads of the records inbox

**Server:** official reference `filesystem` MCP server
(`npx -y @modelcontextprotocol/server-filesystem records_inbox/`).

**Why borrow instead of build:** schools' incoming records are files (term-result
CSV exports, scanned report cards, remark book dumps). Sandboxing file access to
one directory, with path-validation we do not have to maintain, is a solved
problem — the official server gives the agent `list_directory` / `read_text_file`
over `records_inbox/` only. Our own server never gains a file-read tool, so a
bug in our code cannot read anything outside the inbox.

The agent's `--from-inbox` run (`agent/inbox.py`) uses this server as its primary
transport; if Node is unavailable it falls back to a direct read-only listing and
labels the trace accordingly.

## Boundary between the servers (kept deliberately clean)

| Server | Role | Writes? |
|---|---|---|
| `longview_mcp` (ours) | Domain tools: ingest, cited profile updates, pattern flags, summaries, approvals, share gate | yes - but gated and audited |
| official `sqlite` (borrowed) | Generic read/exploratory SQL over raw history | no (read-only usage) |
| official `filesystem` (borrowed) | Sandboxed reads of `records_inbox/` (exports, scans, remark books) | no (read-only usage) |

A stranger could reuse either half without the other. Our tool logic
(`longview_mcp/core.py`) is stdlib-only and has no dependency on the agent
framework or the borrowed server.

## Wiring all three into an MCP client

The repo ships a ready `mcp_config.json` (same shape, plus notes). Add all three servers to any MCP client config:

```json
{
  "mcpServers": {
    "longview": {
      "command": "python",
      "args": ["-m", "longview_mcp.server"],
      "cwd": "."
    },
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "data/longview.db"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "records_inbox/"]
    }
  }
}
```

Note: because the borrowed server is generic SQL, the demo shows the agent
preferring our typed tools for anything it might write, and reaching for the
borrowed server only for exploratory reads ("what does Y3 attendance look
like across the class?").
