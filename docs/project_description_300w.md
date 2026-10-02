# Project description (≈300 words, for the submission form)

## Mzizi — The Long-View Learner Agent

Across African schools, a learner's story is scattered across attendance registers,
paper report cards, teacher remark books and exam slips. When a child changes
school — or a new term starts — the picture resets, and decisions about placement,
support and promotion rest on a single exam snapshot. Mzizi (repo package name:
`longview`) is an agentic AI system that builds and maintains a longitudinal,
evidence-cited record of each learner from the messy records schools already have.

The agent is a Python pipeline — ingest, analyse, update profile, flag patterns,
draft summary — orchestrated with LangGraph. It is a real MCP client: it chooses
among 9 domain tools on our custom FastMCP server and reaches for two borrowed
official servers (SQLite for exploratory reads, Filesystem for sandboxed reads of
the school's records inbox). Everything runs on an ordinary 8 GB-RAM school laptop:
the drafting language model is a quantized Qwen 2.5 1.5B/3B served locally by
Ollama — no cloud LLM APIs, works offline, no cron jobs; every run is
teacher-triggered.

Two rules are enforced in code, not prompts. First, the agent can never score a
learner, and every conclusion it writes must cite the evidence record IDs behind
it — tool schemas and database guards reject unsourced claims before they are
stored. Second, nothing leaves the school without a named human approving it:
the FastAPI review UI shows every flag and draft summary next to the exact quiz,
term and score it came from, and the agent cannot approve its own gate. In
production, the same rules are mirrored in typed Convex write-functions with
schema and migrations.

We validate honestly: 11 eval tasks run on fresh synthetic cohorts, 10 stable
passes, and one documented known failure (a typoed Kiswahili note) that we kept
and explained. All data is synthetic. Teachers save hours on reports; guardians
receive plain-language, translated-ready updates; learners get help before they
fail — the long view, on hardware schools already own.
