"""CLI runner - one full agent task end-to-end, tool calls printed for the demo video.

Examples:
    python -m agent.run --learner L002 --simulate
    python -m agent.run --learner L003 --no-llm
    python -m agent.run --learner auto
    python -m agent.run --from-inbox   # pick up a term export from records_inbox/
"""

import argparse
import json
import random

from agent import graph
from agent import inbox
from longview_mcp import core


def pick_learner(conn) -> str:
    """auto: the declining reader (L002) is the canonical demo learner."""
    return "L002"


def simulate_trigger(learner_id: str) -> dict:
    """A fresh reading quiz result arriving today - the 'new event' that wakes the agent."""
    random.seed()
    return {"kind": "quiz", "subject": "english", "skill": "reading",
            "term": "Y4T3", "value": round(random.uniform(38, 55), 1),
            "detail": "reading comprehension quiz", "source_ref": None}


def print_trace(state: dict) -> None:
    print("\n=== PLAN ===")
    print("  " + " -> ".join(state.get("plan", [])))
    print("\n=== TOOL CALL TRACE ===")
    for step in state.get("trace", []):
        if "node" in step:
            print(f"[{step['node']}] {step.get('message', step.get('plan', step.get('error', '')))}")
        else:
            mark = "OK " if step["ok"] else "ERR"
            extra = "" if step["ok"] else f"  {step.get('error', step.get('refused', ''))}"
            print(f"  {mark} {step['tool']} (attempt {step['attempt']}){extra}")
            if step["ok"] and isinstance(step["result"], dict):
                brief = {k: v for k, v in step["result"].items() if k != "evidence_ids"}
                if step["result"].get("evidence_ids"):
                    brief["evidence_ids"] = f"{len(step['result']['evidence_ids'])} cited"
                print(f"       {json.dumps(brief, default=str)[:160]}")
    print("\n=== FINDINGS ===")
    for f in state.get("findings", []):
        print(f"  - [{f['pattern_type']}] {f['rationale']}")
    print("\n=== OUTCOME ===")
    print(f"  summary_id   : {state.get('summary_id')}")
    print(f"  approval_id  : {state.get('approval_id')}  (named human decides in the review UI)")
    print(f"  awaiting     : {'YES - human gate' if state.get('awaiting_human') else 'no'}")
    if state.get("error"):
        print(f"  ERROR        : {state['error']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--learner", default="auto")
    ap.add_argument("--simulate", action="store_true",
                    help="ingest a fresh quiz result before running")
    ap.add_argument("--no-llm", action="store_true", help="use the template drafter")
    ap.add_argument("--from-inbox", action="store_true",
                    help="read the first pending export in records_inbox/ via the "
                         "official filesystem MCP server and run on its newest row")
    args = ap.parse_args()

    inbox_note = None
    if args.from_inbox:
        name, triggers, transport = inbox.next_pending_export()
        if not name:
            print("records_inbox/: no pending export found (drop a *.csv in the folder).")
            return
        print(f"records_inbox: read {name} via {transport}")
        conn = core.open_db()
        try:
            for t in triggers[:-1]:   # older rows: bulk-imported as raw evidence
                c = core.open_db()
                try:
                    core.ingest_result(conn=c, actor="records_inbox", **t)
                finally:
                    c.close()
            print(f"  bulk-imported {max(len(triggers) - 1, 0)} earlier row(s) as raw evidence")
        finally:
            conn.close()
        args.learner = triggers[-1]["learner_id"]
        trigger = triggers[-1]      # newest row wakes the agent
        trigger["value"] = trigger.get("value") or round(random.uniform(38, 55), 1)
        inbox_note = name
    else:
        trigger = None

    if not args.from_inbox:
        conn = core.open_db()
        try:
            learner_id = pick_learner(conn) if args.learner == "auto" else args.learner
        finally:
            conn.close()
    else:
        learner_id = args.learner

    if trigger is None and args.simulate:
        trigger = simulate_trigger(learner_id)
    if trigger:
        print(f"New event for {learner_id}: {trigger['kind']} / {trigger['skill']} "
              f"/ {trigger['term']} / score {trigger['value']}")

    state = graph.run(learner_id, trigger, use_llm=not args.no_llm)
    print_trace(state)

    print("\nNext step: python -m ui.app  ->  review flags, approve sharing with your name.")


if __name__ == "__main__":
    main()
