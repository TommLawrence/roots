"""Eval runner: N tasks x R repetitions against freshly generated synthetic cohorts.

Writes evals/results/EVALS_REPORT.md + results.json with pass rates and
run-to-run variation. No cherry-picking: every repetition is reported.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 2)[0])

from evals.tasks import TASKS
from longview_mcp.db import connect


def build_eval_db(db_path: str, seed: int, learners: int) -> None:
    from datagen.generate import generate
    conn = connect(db_path)
    try:
        generate(conn, learners, seed)
    finally:
        conn.close()


def run(reps: int, learners: int, seed: int) -> dict:
    results = {tid: {"title": title, "passes": 0, "details": [], "known_fail": "KNOWN" in title,
                     "llm_free": not needs_llm}
               for tid, title, _, needs_llm in TASKS}
    timings = []

    for rep in range(1, reps + 1):
        db_path = os.path.join("data", f"evals_rep{rep}.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        t0 = time.time()
        build_eval_db(db_path, seed + rep, learners)
        timings.append(round(time.time() - t0, 1))
        conn = connect(db_path)
        try:
            for tid, title, fn, needs_llm in TASKS:
                try:
                    ok, detail = fn(conn)
                except Exception as exc:               # a crashed task is a failed task
                    ok, detail = False, f"task crashed: {type(exc).__name__}: {exc}"
                results[tid]["passes"] += int(bool(ok))
                results[tid]["details"].append(detail)
        finally:
            conn.close()
        os.remove(db_path)

    return {"results": results, "reps": reps, "learners": learners, "seed_base": seed,
            "build_seconds_per_rep": timings}


def write_report(outcome: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    lines = ["# EVALS report", "",
             f"Repetitions: {outcome['reps']} (fresh cohort per rep, seeds "
             f"{outcome['seed_base']}+1..{outcome['seed_base'] + outcome['reps']}, "
             f"{outcome['learners']} learners each)  ",
             f"Cohort build time per rep: {outcome['build_seconds_per_rep']}s", "",
             "| ID | Task | Pass rate | Variation | Status | Detail |",
             "|----|------|-----------|-----------|--------|--------|"]
    for tid, r in outcome["results"].items():
        rate = f"{r['passes']}/{outcome['reps']}"
        variation = "stable" if r["passes"] in (0, outcome["reps"]) else "VARIES ACROSS RUNS"
        status = ("KNOWN FAIL (documented)" if r["known_fail"] and r["passes"] == 0
                  else "PASS" if r["passes"] == outcome["reps"]
                  else "FAIL" if r["passes"] == 0 else f"FLAKY {rate}")
        lines.append(f"| {tid} | {r['title']} | {rate} | {variation} | {status} | "
                     f"{r['details'][0]} |")
    report = "\n".join(lines) + "\n"
    with open(os.path.join(out_dir, "EVALS_REPORT.md"), "w") as fh:
        fh.write(report)
    with open(os.path.join(out_dir, "results.json"), "w") as fh:
        json.dump(outcome, fh, indent=2, default=str)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--learners", type=int, default=80)
    ap.add_argument("--seed", type=int, default=100)
    args = ap.parse_args()

    outcome = run(args.reps, args.learners, args.seed)
    report = write_report(outcome, os.path.join("evals", "results"))
    print(report)


if __name__ == "__main__":
    main()
