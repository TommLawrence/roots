"""HTML rendering for the review UI.

Pure string templates (no template engine, no client framework - this must
run on an 8 GB laptop in one command). Kept separate so app.py stays thin.
Every dynamic value passes through _esc; evidence links point at /evidence.
"""

import json

CSS = """
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; margin: 0; background: #f6f4ef; color: #1c1c1c; }
  header { background: #7a3b12; color: #fff; padding: 0 24px; }
  header .bar { max-width: 980px; margin: 0 auto; display: flex; align-items: center;
                gap: 22px; height: 54px; }
  header .brand { font-weight: 700; font-size: 18px; letter-spacing: .2px; }
  header nav a { color: #f3e3cf; text-decoration: none; font-size: 14px; padding: 6px 2px;
                 border-bottom: 2px solid transparent; }
  header nav a.on { color: #fff; border-bottom-color: #f3b562; }
  main { max-width: 980px; margin: 22px auto 60px; padding: 0 16px; }
  h2 { border-bottom: 2px solid #e5d9c3; padding-bottom: 6px; margin-top: 34px; font-size: 18px; }
  .card { background: #fff; border: 1px solid #ddd; border-radius: 10px;
          padding: 14px 18px; margin-bottom: 14px; }
  .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 12px; margin-bottom: 8px; }
  .kpi { background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 12px 16px; }
  .kpi b { font-size: 26px; display: block; }
  .kpi span { color: #777; font-size: 12px; }
  .pill { background: #eee4d2; padding: 2px 10px; border-radius: 99px; font-size: 12px;
          white-space: nowrap; }
  .pill.pending { background: #fde68a; } .pill.approved, .pill.raised { background: #bbf7d0; }
  .pill.rejected, .pill.dismissed { background: #fecaca; }
  .pill.shared { background: #bfdbfe; } .pill.draft { background: #e9d5ff; }
  .pill.strength { background: #bbf7d0; } .pill.weakness { background: #fecaca; }
  .muted { color: #777; font-size: 12px; }
  pre.summary { white-space: pre-wrap; background: #faf8f3; padding: 12px;
                border-radius: 8px; font-family: inherit; border: 1px solid #eee2cc; }
  input { padding: 7px 9px; border: 1px solid #ccc; border-radius: 6px; }
  button { padding: 7px 14px; border: 0; border-radius: 6px; cursor: pointer; }
  button.ok { background: #166534; color: #fff; }
  button.bad { background: #991b1b; color: #fff; }
  button.flat { background: #eee4d2; color: #4a2c12; }
  .error { background: #fee2e2; border: 1px solid #fca5a5; padding: 10px 14px;
           border-radius: 8px; margin: 14px 0; }
  .flash { background: #dcfce7; border: 1px solid #86efac; padding: 10px 14px;
           border-radius: 8px; margin: 14px 0; }
  table { border-collapse: collapse; width: 100%; background: #fff; border-radius: 10px;
          overflow: hidden; border: 1px solid #ddd; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee;
           font-size: 13px; vertical-align: top; }
  th { background: #f0e9dc; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }
  tr:last-child td { border-bottom: 0; }
  a { color: #9a4a12; }
  .chip { display: inline-block; background: #faf3e4; border: 1px solid #e8d9b8;
          border-radius: 6px; padding: 2px 8px; margin: 2px 4px 2px 0; font-size: 12px;
          font-family: ui-monospace, monospace; text-decoration: none; color: #5b3a10; }
  .chip:hover { border-color: #7a3b12; }
  .spark { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .spark .labels { font-size: 12px; color: #666; max-width: 320px; }
  footer { max-width: 980px; margin: 30px auto; padding: 0 16px; color: #8a8377; font-size: 12px; }
"""


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _layout(title, active, body):
    def nav(href, key, label):
        cls = ' class="on"' if key == active else ""
        return f'<a href="{href}"{cls}>{label}</a>'

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{CSS}</style></head><body>
<header><div class="bar">
  <span class="brand">Longview</span>
  <nav>{nav("/", "dash", "Dashboard")} {nav("/learners", "learners", "Learners")}
       {nav("/audit", "audit", "Audit log")}</nav>
</div></header>
<main>
{body}
</main>
<footer>The agent proposes - a named human decides. Every action on this page,
including refusals, is written to the audit log with a timestamp.</footer>
</body></html>"""


def _flash(error=None, ok=None):
    html = f'<div class="error"><b>Refused:</b> {_esc(error)}</div>' if error else ""
    html += f'<div class="flash">{_esc(ok)}</div>' if ok else ""
    return html


def _ev_chip(e) -> str:
    """A citation chip: source_ref text, links to the raw record."""
    label = e.get("source_ref") or f"event {e.get('id')}"
    extra = ""
    if e.get("value") is not None:
        extra = f" = {e['value']:g}"
    return (f'<a class="chip" href="/evidence?id={int(e["id"])}" '
            f'title="{_esc(e.get("kind", ""))} | {_esc(e.get("term", ""))}">'
            f'{_esc(label)}{_esc(extra)}</a>')


def sparkline_svg(series, fmt=str, width=190, height=48, color="#7a3b12"):
    """Inline SVG polyline for [(term, value)] - server-rendered, no JS."""
    pts = [(t, float(v)) for t, v in series if v is not None]
    if len(pts) < 2:
        return '<span class="muted">not enough terms yet</span>'
    values = [v for _, v in pts]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pad = 14
    step = (width - 2 * pad) / (len(pts) - 1)
    coords, dots = [], []
    for i, (term, v) in enumerate(pts):
        x = pad + i * step
        y = height - pad - ((v - lo) / span) * (height - 2 * pad)
        coords.append(f"{x:.1f},{y:.1f}")
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{color}"/>')
    first, last = pts[0], pts[-1]
    prev = pts[-2] if len(pts) > 1 else last
    tips = " · ".join(f"{t}: {fmt(v)}" for t, v in pts)
    return (f'<svg width="{width}" height="{height}" role="img" aria-label="trend">'
            f'<title>{_esc(tips)}</title>'
            f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
            f'{"".join(dots)}</svg>'
            f'<span class="labels"><b>{_esc(fmt(last[1]))}</b> now · '
            f'{_esc(fmt(first[1]))} at {_esc(first[0])} · '
            f'{_esc(prev[0])} → {_esc(last[0])}</span>')


# ---------------------------------------------------------------- pages

def render_dashboard(counts, flags, gates, shared, error=None, ok=None) -> str:
    tiles = "".join(
        f'<div class="kpi"><b>{v}</b><span>{k.replace("_", " ")}</span></div>'
        for k, v in counts.items())

    flag_html = ""
    for f in flags:
        ev = json.loads(f["evidence_ids"]) if f.get("evidence_ids") else []
        chips = "".join(_ev_chip({"id": i, "source_ref": f"event {i}"}) for i in ev[:6])
        flag_html += f"""
      <div class="card">
        <div class="row"><a href="/learner/{_esc(f['learner_id'])}"><b>{_esc(f['name'])}</b></a>
          <span class="pill pending">{_esc(f['pattern_type'])}</span>
          <span class="muted">{_esc(str(f['created_at'])[:16])}</span></div>
        <p>{_esc(f['rationale'])}</p>
        <div>{chips}</div>
        <form method="post" action="/flag/resolve" class="row">
          <input type="hidden" name="flag_id" value="{int(f['id'])}">
          <label class="muted">Your name:</label>
          <input name="decided_by" placeholder="e.g. Ms. Wanjiru" required>
          <button name="decision" value="raised" class="ok">Raise (act on it)</button>
          <button name="decision" value="dismissed" class="bad">Dismiss</button>
        </form>
      </div>"""

    gate_html = ""
    for a in gates:
        s = a.get("summary") or {}
        status = a["status"]
        name = s.get("name", "(summary missing)")
        head = (f'<div class="row"><a href="/gate/{int(a["id"])}">'
                f'<b>{_esc(name)}</b></a> '
                f'<span class="pill {status}">{status}</span>'
                f'<span class="muted">approval #{int(a["id"])}</span></div>')
        if status == "pending":
            gate_html += f"""
      <div class="card">{head}
        <pre class="summary">{_esc((s.get('body') or '')[:220])}...</pre>
        <div class="row"><a href="/gate/{int(a['id'])}">Open the gate - read citations, then decide</a></div>
      </div>"""
        elif status == "approved":
            gate_html += f"""
      <div class="card">{head}
        <pre class="summary">{_esc((s.get('body') or '')[:220])}...</pre>
        <form method="post" action="/share" class="row">
          <input type="hidden" name="summary_id" value="{int(a['summary_id'] or 0)}">
          <button class="ok">Send to guardian (SMS)</button>
          <span class="muted">approved by {_esc(a.get('decided_by') or '')}</span>
        </form>
      </div>"""
        else:
            gate_html += f"""
      <div class="card">{head}
        <span class="muted">rejected by {_esc(a.get('decided_by') or '')}
        {_esc(str(a.get('decided_at') or '')[:16])}</span>
      </div>"""

    shared_html = "".join(
        f"<li><a href=\"/learner/{_esc(s['learner_id'])}\">{_esc(s['name'])}</a> - "
        f"summary #{int(s['id'])} shared "
        f"<span class='muted'>(audit log has the approval)</span></li>"
        for s in shared)

    return _layout("Longview - Teacher Review", "dash", f"""
  {_flash(error, ok)}
  <h2>This week</h2>
  <div class="grid">{tiles}</div>
  <h2>Flags awaiting review ({len(flags)})</h2>
  <p class="muted">Patterns the agent noticed in the records. Discuss with the learner
  and guardian before acting - the agent only proposes.</p>
  {flag_html or '<p class="muted">No pending flags.</p>'}
  <h2>Sharing gate ({sum(1 for a in gates if a['status'] == 'pending')} pending)</h2>
  <p class="muted">Nothing leaves the classroom unless you open the gate and type your name.</p>
  {gate_html or '<p class="muted">No share requests.</p>'}
  <h2>Recently shared</h2>
  <ul>{shared_html or '<span class="muted">Nothing shared yet.</span>'}</ul>""")


def render_roster(rows) -> str:
    body = ""
    for r in rows:
        flag_cell = (f'<span class="pill pending">{int(r["pending_flags"])} pending</span>'
                     if r["pending_flags"] else "-")
        body += (f"<tr><td><a href=\"/learner/{_esc(r['id'])}\">{_esc(r['id'])}</a></td>"
                 f"<td>{_esc(r['name'])}</td><td>{_esc(r.get('guardian') or '-')}</td>"
                 f"<td>{_esc(r.get('cohort_year') or '-')}</td>"
                 f"<td>{int(r['events'])}</td><td>{int(r['entries'])}</td>"
                 f"<td>{flag_cell}</td></tr>")
    return _layout("Longview - Learners", "learners", f"""
  <h2>Learners ({len(rows)})</h2>
  <p class="muted">Synthetic cohort. Open a learner to see the cited profile,
  patterns over time, and any pending decisions.</p>
  <table><tr><th>Code</th><th>Name</th><th>Guardian</th><th>Cohort</th>
  <th>Records</th><th>Profile entries</th><th>Flags</th></tr>{body}</table>""")


def render_learner(learner_row, series, attendance, entries, flags, summaries,
                   error=None, ok=None) -> str:
    lid = learner_row["id"]

    spark_html = ""
    for key, pts in series.items():
        spark_html += (f'<div class="card"><div class="spark"><b>{_esc(key)}</b>'
                       f'{sparkline_svg([(t, v) for t, v, _ in pts])}'
                       f'<span class="muted">{pts[-1][2]} records in latest term</span>'
                       f'</div></div>')
    if attendance:
        att_svg = sparkline_svg([(t, v) for t, v, _ in attendance],
                                fmt=lambda v: f"{v * 100:.0f}%")
        spark_html += ('<div class="card"><div class="spark">'
                       '<b>attendance</b>' + att_svg +
                       '<span class="muted">mean attendance per term</span></div></div>')
    if not spark_html:
        spark_html = '<p class="muted">No scored records yet.</p>'

    entry_html = ""
    for e in entries:
        chips = "".join(_ev_chip(ev) for ev in e["evidence"])
        entry_html += f"""
      <div class="card">
        <div class="row"><span class="pill {_esc(e['kind'])}">{_esc(e['kind'])}</span>
          <span class="muted">added by {_esc(e['created_by'])}
          {_esc(str(e.get('created_at') or '')[:16])}</span></div>
        <p>{_esc(e['claim'])}</p>
        <div>{chips}</div>
      </div>"""

    flag_html = ""
    for f in flags:
        if f["status"] == "pending_review":
            flag_html += f"""
      <div class="card">
        <div class="row"><span class="pill pending">{_esc(f['pattern_type'])}</span>
          <span class="muted">{_esc(str(f['created_at'])[:16])}</span></div>
        <p>{_esc(f['rationale'])}</p>
        <form method="post" action="/flag/resolve" class="row">
          <input type="hidden" name="flag_id" value="{int(f['id'])}">
          <label class="muted">Your name:</label>
          <input name="decided_by" placeholder="e.g. Ms. Wanjiru" required>
          <button name="decision" value="raised" class="ok">Raise</button>
          <button name="decision" value="dismissed" class="bad">Dismiss</button>
        </form>
      </div>"""
        else:
            flag_html += f"""
      <div class="card"><div class="row">
        <span class="pill {_esc(f['status'])}">{_esc(f['pattern_type'])}</span>
        <span class="muted">{_esc(f['status'])} by {_esc(f.get('decided_by') or '-')}
        {_esc(str(f.get('decided_at') or '')[:16])}</span></div>
        <p>{_esc(f['rationale'])}</p></div>"""

    summary_html = ""
    for s in summaries:
        a = s.get("approval")
        if a and a["status"] == "pending":
            action = f'<a href="/gate/{int(a["id"])}">open gate #{int(a["id"])}</a>'
        elif a and a["status"] == "approved":
            action = (f'<form method="post" action="/share" class="row">'
                      f'<input type="hidden" name="summary_id" value="{int(s["id"])}">'
                      f'<button class="ok">Send to guardian</button></form>')
        else:
            action = f'<a href="/audit">see audit log</a>'
        summary_html += f"""
      <div class="card">
        <div class="row"><span class="pill {_esc(s['status'])}">{_esc(s['status'])}</span>
          <span class="muted">summary #{int(s['id'])} · {_esc(str(s['created_at'])[:16])}
          · drafted by {_esc(s['created_by'])}</span></div>
        <pre class="summary">{_esc(s['body'])}</pre>
        <div class="row">{action}</div>
      </div>"""

    return _layout(f"Longview - {learner_row['name']}", "learners", f"""
  {_flash(error, ok)}
  <h2>{_esc(learner_row['name'])} <span class="muted">({_esc(lid)} · guardian:
  {_esc(learner_row.get('guardian') or '-')})</span></h2>
  <h2>Patterns over time</h2>
  {spark_html}
  <h2>Cited profile ({len(entries)})</h2>
  <p class="muted">Every claim carries the records it came from. No entry, no label.</p>
  {entry_html or '<p class="muted">No profile entries yet.</p>'}
  <h2>Flags ({len(flags)})</h2>
  {flag_html or '<p class="muted">No flags for this learner.</p>'}
  <h2>Summaries ({len(summaries)})</h2>
  {summary_html or '<p class="muted">No summaries drafted yet.</p>'}""")


def render_gate(detail, error=None, ok=None) -> str:
    a = detail["approval"]
    s = detail["summary"] or {}
    status = a["status"]

    findings_html = ""
    for f in detail["findings"]:
        chips = "".join(_ev_chip(ev) for ev in f["evidence"])
        findings_html += (f"<tr><td><span class=\"pill pending\">"
                          f"{_esc(f['pattern_type'])}</span></td>"
                          f"<td>{_esc(f.get('skill') or '-')}</td>"
                          f"<td>{chips or '<span class=muted>none</span>'}</td></tr>")

    entries_html = ""
    for e in detail["profile_entries"]:
        chips = "".join(_ev_chip(ev) for ev in e["evidence"])
        entries_html += (f"<tr><td><span class=\"pill {_esc(e['kind'])}\">"
                         f"{_esc(e['kind'])}</span></td><td>{_esc(e['claim'])}</td>"
                         f"<td>{chips or '<span class=muted>none</span>'}</td></tr>")

    if status == "pending":
        form = f"""
      <form method="post" action="/resolve" class="card">
        <input type="hidden" name="approval_id" value="{int(a['id'])}">
        <p><b>Your decision becomes part of the audit log, with your name on it.</b></p>
        <div class="row">
          <label>Your name (required):</label>
          <input name="decided_by" placeholder="e.g. Ms. Wanjiru" required>
          <input name="note" placeholder="optional note for the record">
        </div>
        <div class="row" style="margin-top:10px">
          <button name="decision" value="approved" class="ok">Approve sharing</button>
          <button name="decision" value="rejected" class="bad">Reject</button>
        </div>
      </form>"""
    elif status == "approved":
        form = f"""
      <div class="card">
        <p><b>Approved by {_esc(a.get('decided_by') or '-')}</b>
        <span class="muted">{_esc(str(a.get('decided_at') or '')[:16])}</span></p>
        <form method="post" action="/share" class="row">
          <input type="hidden" name="summary_id" value="{int((detail['summary'] or {}).get('id') or 0)}">
          <button class="ok">Send to guardian (SMS)</button>
          <span class="muted">guardian on record: {_esc(s.get('guardian') or '-')}</span>
        </form>
      </div>"""
    else:
        form = (f'<div class="card"><p>Rejected by {_esc(a.get("decided_by") or "-")}. '
                f'<span class="muted">{_esc(a.get("note") or "")}</span></p></div>')

    return _layout(f"Longview - Gate #{int(a['id'])}", "dash", f"""
  {_flash(error, ok)}
  <p><a href="/learner/{_esc(s.get('learner_id') or '')}">&larr; back to
  {_esc(s.get('name') or 'learner')}</a></p>
  <h2>Sharing gate #{int(a['id'])} <span class="pill {status}">{status}</span></h2>
  <p class="muted">requested {_esc(str(a['requested_at'])[:16])} · summary
  #{int((detail['summary'] or {}).get('id') or 0)} for {_esc(s.get('name') or '-')}</p>
  <pre class="summary">{_esc(s.get('body') or '(summary missing)')}</pre>
  <h2>Where each point comes from</h2>
  <p class="muted">Every line above resolves to these raw records. If a claim here
  has no record behind it, reject the gate - that is what it is for.</p>
  <table><tr><th>Pattern</th><th>Skill</th><th>Evidence (raw records)</th></tr>{findings_html}</table>
  <h2>Cited profile entries used</h2>
  <table><tr><th>Kind</th><th>Claim</th><th>Evidence</th></tr>{entries_html}</table>
  <h2>Decision</h2>
  {form}""")


def render_evidence(row, back_to) -> str:
    fields = "".join(
        f"<tr><th>{_esc(k)}</th><td>{_esc(v if v is not None else '-')}</td></tr>"
        for k, v in row.items() if k not in ("id", "learner_id"))
    return _layout(f"Longview - Record #{int(row['id'])}", "learners", f"""
  <p><a href="{_esc(back_to)}">&larr; back</a></p>
  <h2>Raw record #{int(row['id'])}</h2>
  <p class="muted">This is the source a citation points at. It is never edited by
  the agent - raw records are append-only.</p>
  <table><tr><th>learner</th><td><a href="/learner/{_esc(row['learner_id'])}"
  >{_esc(row['learner_id'])}</a></td></tr>{fields}</table>""")


def render_audit(rows, total, limit, offset) -> str:
    body = ""
    for r in rows:
        try:
            result = json_short(r["result"])
        except Exception:
            result = str(r["result"])
        body += (f"<tr><td class='muted'>{_esc(str(r['ts'])[:19])}</td>"
                 f"<td>{_esc(r['actor'])}</td><td><b>{_esc(r['tool'])}</b></td>"
                 f"<td class='muted'>{_esc(json_short(r['args']))}</td>"
                 f"<td>{_esc(result)}</td></tr>")
    newer = max(0, offset - limit)
    older = offset + limit
    pager = (f'<div class="row" style="margin-top:12px">'
             f'<a href="/audit?limit={limit}&amp;offset={newer}">&larr; newer</a> '
             f'<span class="muted">rows {offset + 1}&ndash;'
             f'{min(offset + limit, total)} of {total}</span> '
             f'<a href="/audit?limit={limit}&amp;offset={older}">older &rarr;</a></div>')

    return _layout("Longview - Audit log", "audit", f"""
  <h2>Audit log</h2>
  <p class="muted">Every tool call, every refusal, every human decision - newest first.</p>
  <table><tr><th>When (UTC)</th><th>Actor</th><th>Tool</th><th>Args</th><th>Result</th></tr>
  {body}</table>
  {pager if total > limit else ''}""")


def json_short(raw, width=110) -> str:
    text = raw if isinstance(raw, str) else str(raw)
    return text if len(text) <= width else text[:width - 1] + "…"


def render_404(what: str) -> str:
    return _layout("Longview - Not found", "", f"""
  <h2>Not found</h2><p>{_esc(what)}</p>
  <p><a href="/">Back to the dashboard</a></p>""")
