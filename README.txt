Longview - teacher review UI (offline snapshot)
Generated 2026-10-05 from the real demo database (80 learners, 12 terms).

Open index.html in any browser. Start here:
  index.html          -> dashboard: pending share gate + open flag
  learner_L002.html   -> Baraka V.: cited profile, reading-decline flag
  gate_1.html         -> the human approval gate (with evidence tables)
  audit_50_0.html     -> the tool-call audit trail

Approve/reject/share buttons are disabled in this snapshot on purpose:
they need the live server so a named human can be recorded in the audit
log. To run the live UI:  cd long-view && make ui   (then visit
http://localhost:8080)
