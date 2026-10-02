"""Records inbox: parser, pending-selection, and read-only fallback listing.

The npx/filesystem-MCP transport is exercised manually (`python -m agent.run
--from-inbox` with Node present); tests stay offline-deterministic and cover
the pure logic plus the labelled fallback.
"""

import pytest

from agent import inbox


SAMPLE = (
    "learner_id,kind,subject,skill,term,value,detail,source_ref\n"
    "L003,quiz,mathematics,fractions,Y4T2,52.5,term 2 exam,term_export.csv\n"
    "L003,quiz,mathematics,fractions,Y4T3,47.0,term 3 exam,term_export.csv\n"
    "L003,quiz,mathematics,fractions,Y4T3,,missing score row,term_export.csv\n"
)


def test_parse_export_maps_all_rows_and_defaults():
    triggers = inbox.parse_export(SAMPLE, "term_export.csv")
    assert len(triggers) == 3
    first = triggers[0]
    assert first["learner_id"] == "L003"
    assert first["value"] == 52.5
    assert first["source_ref"] == "term_export.csv"
    # row without a score still imports (value None), never crashes
    assert triggers[2]["value"] is None
    assert triggers[2]["detail"] == "missing score row"


def test_parse_export_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        inbox.parse_export("learner_id,kind\nL001,quiz\n", "bad.csv")


def test_parse_export_skips_blank_learner_rows():
    text = SAMPLE + ",quiz,math,reading,Y4T3,50.0,,term_export.csv\n"
    assert len(inbox.parse_export(text, "term_export.csv")) == 3


def test_fallback_listing_is_labelled(tmp_path, monkeypatch):
    (tmp_path / "sample_term_export.csv").write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("n", encoding="utf-8")
    monkeypatch.setattr(inbox, "INBOX", tmp_path)
    entries, transport = inbox._list_fallback()
    assert "sample_term_export.csv" in entries and "notes.txt" in entries
    assert "fallback" in transport or "unavailable" in transport


def test_next_pending_export_prefers_csv_and_parses(tmp_path, monkeypatch):
    (tmp_path / "readme.md").write_text("not an export", encoding="utf-8")
    (tmp_path / "sample_term_export.csv").write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(inbox, "INBOX", tmp_path)
    monkeypatch.setattr(inbox, "list_inbox", lambda: (["readme.md", "sample_term_export.csv"],
                                                      "test transport"))
    name, triggers, transport = inbox.next_pending_export()
    assert name == "sample_term_export.csv"
    assert len(triggers) == 3
    assert transport == "test transport"


def test_mark_done_hides_file_from_selection(tmp_path, monkeypatch):
    (tmp_path / "a.csv").write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(inbox, "INBOX", tmp_path)
    inbox.mark_done("a.csv")
    assert (tmp_path / "a.csv.done").exists()
    entries, _ = inbox._list_fallback()
    assert "a.csv.done" in entries      # renamed, kept for the record
    assert "a.csv" not in entries       # no longer pending


def test_next_pending_export_skips_done_files(tmp_path, monkeypatch):
    (tmp_path / "a.csv.done").write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "b.csv").write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(inbox, "INBOX", tmp_path)
    monkeypatch.setattr(inbox, "list_inbox", lambda: (["a.csv.done", "b.csv"], "t"))
    name, _, _ = inbox.next_pending_export()
    assert name == "b.csv"
