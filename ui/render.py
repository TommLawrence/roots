"""HTML rendering for the review UI (kept separate so app.py stays thin)."""


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def render_index(flags, gates, shared, error=None) -> str:
    flag_html = ""
    for f in flags:
        flag_html += f"""
      <div class="card">
        <div class="row"><b>{_esc(f['name'])}</b>
          <span class="pill">{_esc(f['pattern_type'])}</span>
          <span class="muted">{_esc(f['created_at'][:16])}</span></div>
        <p>{_esc(f['rationale'])}</p>
        <p class="muted">Discuss with the learner and guardian before acting. The agent only proposes.</p>
      </div>"""

    gate_html = ""
    for a in gates:
        s = a.get("summary") or {}
        if a["status"] == "pending":
            gate_html += f"""
      <div class="card">
        <div class="row"><b>{_esc(s.get('name', ''))}</b>
          <span class="pill pending">awaiting decision</span>
          <span class="muted">approval #{a['id']}</span></div>
        <pre class="summary">{_esc(s.get('body', ''))}</pre>
        <form method="post" action="/resolve" class="row">
          <input type="hidden" name="approval_id" value="{a['id']}">
          <label>Your name (required):</label>
          <input name="decided_by" placeholder="e.g. Ms. Wanjiru" required>
          <button name="decision" value="approved" class="ok">Approve sharing</button>
          <button name="decision" value="rejected" class="bad">Reject</button>
          <input name="note" placeholder="optional note">
        </form>
      </div>"""
        else:
            gate_html += f"""
      <div class="card">
        <div class="row"><b>{_esc(s.get('name', ''))}</b>
          <span class="pill approved">approved by {_esc(a.get('decided_by', ''))}</span>
          <span class="muted">approval #{a['id']}</span></div>
        <pre class="summary">{_esc(s.get('body', ''))}</pre>
        <form method="post" action="/share" class="row">
          <input type="hidden" name="summary_id" value="{s.get('id', '')}">
          <button class="ok">Send to guardian (SMS)</button>
        </form>
      </div>"""

    shared_html = ""
    for s in shared:
        shared_html += (f"<li><b>{_esc(s['name'])}</b> - shared at "
                        f"{_esc(s['id'])} <span class='muted'>(see audit log)</span></li>")

    error_html = f'<div class="error">{_esc(error)}</div>' if error else ""

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Longview - Teacher Review</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #f6f4ef; color: #1c1c1c; }}
  header {{ background: #7a3b12; color: #fff; padding: 14px 24px; }}
  main {{ max-width: 860px; margin: 24px auto; padding: 0 16px; }}
  .card {{ background: #fff; border: 1px solid #ddd; border-radius: 10px;
          padding: 14px 18px; margin-bottom: 14px; }}
  .row {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
  .pill {{ background: #eee4d2; padding: 2px 10px; border-radius: 99px; font-size: 12px; }}
  .pill.pending {{ background: #fde68a; }} .pill.approved {{ background: #bbf7d0; }}
  .muted {{ color: #777; font-size: 12px; }}
  pre.summary {{ white-space: pre-wrap; background: #faf8f3; padding: 10px;
                border-radius: 8px; font-family: inherit; }}
  input {{ padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; }}
  button {{ padding: 7px 14px; border: 0; border-radius: 6px; cursor: pointer; }}
  button.ok {{ background: #166534; color: #fff; }}
  button.bad {{ background: #991b1b; color: #fff; }}
  .error {{ background: #fee2e2; border: 1px solid #fca5a5; padding: 10px 14px;
           border-radius: 8px; margin-bottom: 14px; }}
  h2 {{ border-bottom: 2px solid #e5d9c3; padding-bottom: 6px; }}
</style></head><body>
<header><h1>Longview - Teacher Review</h1></header>
<main>
  {error_html}
  <h2>Flags awaiting review ({len(flags)})</h2>
  {flag_html or '<p class="muted">No pending flags.</p>'}
  <h2>Sharing gate ({len(gates)})</h2>
  <p class="muted">Nothing leaves the classroom unless you type your name here.</p>
  {gate_html or '<p class="muted">No pending share requests.</p>'}
  <h2>Recently shared</h2>
  <ul>{shared_html or '<span class="muted">Nothing shared yet.</span>'}</ul>
</main></body></html>"""
