# Demo video script (< 3 minutes, one unedited agent run, tool calls on screen)

> Submission requirement: unedited run with tool calls visible - not slides.
> Record the terminal + review UI side by side. No cuts: if it fails, show it.

## Beats

1. **0:00-0:20 - The problem, in one sentence.**
   "A pattern that would be obvious over four years of data is invisible one term
   at a time. Longview watches one learner across terms and hands the teacher a
   sourced profile - never a verdict."

2. **0:20-0:50 - New event arrives.**
   Terminal: `python -m agent.run --learner L002 --simulate --no-llm`
   Narrate the trace as it prints: plan -> ingest -> analyse -> flags -> draft ->
   stops at the human gate. Point at the evidence ids: every claim cites its quiz.

3. **0:50-1:30 - The one rule, live.**
   Show `update_profile` with an empty evidence list being REFUSED (run the
   E02 snippet or `make evals` output on screen). "An unsourced label on a child
   is worse than no label - so the tool refuses, and the refusal itself is
   audit-logged."

4. **1:30-2:20 - The human gate.**
   Open the review UI (http://localhost:8080). Show the flagged pattern with its
   cited terms, the draft summary in plain language. Type your name, approve,
   send. Back to the terminal: the audit log shows named human, timestamp, action.

5. **2:20-2:50 - Honesty + open source.**
   Show EVALS.md: the 5/5 stable rows and the ONE failure we did not fix
   (Kiswahili notes) and what we'd try next. "MIT licensed, `pip install -e .`
   and `make demo` - one command, synthetic data only."

## Before recording

- [ ] `rm -rf data/*.db && make demo` from a clean clone (this is exactly what judges will run)
- [ ] Ollama running with `qwen2.5:3b-instruct-q4_K_M` if we want the LLM drafter on screen
- [ ] Terminal font size up; window clean of unrelated tabs
- [ ] Practise once end-to-end; keep it under 3:00
