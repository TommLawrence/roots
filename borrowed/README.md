# The MCP server we did NOT write

**Server:** official reference `sqlite` MCP server
(`uvx mcp-server-sqlite --db-path data/longview.db`, or the Node equivalent
`@modelcontextprotocol/server-sqlite`).

**Why borrow instead of build (the one line the submission form asks for):**
generic read-only SQL over the records database is a solved, audited problem -
the official server gives the agent ad-hoc query power over the raw history
without us adding a hand-rolled query tool (and its edge cases) to our own
server's attack surface.

**Boundary between the two servers (kept deliberately clean):**

| Server | Role | Writes? |
|---|---|---|
| `longview_mcp` (ours) | Domain tools: ingest, cited profile updates, pattern flags, summaries, approvals, share gate | yes - but gated and audited |
| official `sqlite` (borrowed) | Generic read/exploratory SQL over raw history | no (read-only usage) |

A stranger could reuse either half without the other. Our tool logic
(`longview_mcp/core.py`) is stdlib-only and has no dependency on the agent
framework or the borrowed server.

## Wiring it into an MCP client

Add both servers to any MCP client config:

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
    }
  }
}
```

Note: because the borrowed server is generic SQL, the demo shows the agent
preferring our typed tools for anything it might write, and reaching for the
borrowed server only for exploratory reads ("what does Y3 attendance look
like across the class?").
