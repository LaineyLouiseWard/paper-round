import csv
import json

from paperround.digest import build_html, subject
from paperround.papers import Paper
from paperround.run import run
from paperround.state import LOG_FIELDS, State
from test_judge import ABSTRACT, FakeJev

ENV = {"TYPESAFE_API_KEY": "t", "RESEND_API_KEY": "r", "ZOTERO_API_KEY": "z"}
FLOOD = Paper("Flood forecasts for Ireland", "https://doi.org/10.1/flood", "Journal A", ABSTRACT, "A. Author",
              doi="10.1/flood")
EBIKE = Paper("Class 3 e-bikes in California", "https://x.org/ebike", "Journal A", "We model e-bike trips in cities "
              "across California and their effect on driving.")


class Recorder:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, *args):
        self.calls.append(args)
        if self.fail:
            raise RuntimeError("Resend HTTP 500")


class TitleJev(FakeJev):
    """Relevance answers depend on the paper: only titles containing 'Flood' are about floods."""

    def ask(self, state, questions):
        if "paper" in state and "Flood" not in state["paper"]["title"]:
            self.calls.append(questions)
            return {q: 0.05 for q in questions}, "jev-test"
        return super().ask(state, questions)


class BrokenJev(TitleJev):
    def ask(self, state, questions):
        if "E-bike" in json.dumps(state) or "e-bike" in json.dumps(state):
            raise RuntimeError("HTTP 500 after retries")
        return super().ask(state, questions)


def go(root, cfg, scope, papers, jev=None, send=None, zot=None, failures=()):
    send = send or Recorder()
    zot = zot or (lambda cfg, key, row, tags: "added:K1")
    code = run(root, cfg, scope, env=ENV, today="2026-10-28", fetch=lambda c, k: (list(papers), list(failures)),
               jev=jev or TitleJev({"floods": 0.92}), add_to_zotero=zot, send_email=send)
    return code, send


def test_round_keeps_logs_emails_and_remembers(root, cfg, scope):
    code, send = go(root, cfg, scope, [FLOOD, EBIKE])
    assert code == 0
    rows = State(root).read_log()
    assert [r["title"] for r in rows] == [FLOOD.title]
    r = rows[0]
    assert r["strands"] == "floods" and r["probability"] == "0.92" and r["zotero"] == "added:K1"
    assert r["emailed"] == "2026-10-28" and r["evidence"] in ABSTRACT
    with open(root / "paper_log.csv", newline="") as f:
        assert next(csv.reader(f)) == LOG_FIELDS
    emailed_rows = send.calls[0][3]
    assert [x["title"] for x in emailed_rows] == [FLOOD.title] and send.calls[0][4] == 2
    assert {"doi:10.1/flood", "class 3 ebikes in california"} <= State(root).seen()
    lines = (root / "state" / "judgements.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["kept"] == []


def test_next_round_skips_seen_papers(root, cfg, scope):
    go(root, cfg, scope, [FLOOD, EBIKE])
    code, send = go(root, cfg, scope, [FLOOD, EBIKE])
    assert code == 0 and send.calls[0][3] == [] and send.calls[0][4] == 0
    assert len(State(root).read_log()) == 1


def test_failed_email_is_retried_next_round(root, cfg, scope):
    code, _ = go(root, cfg, scope, [FLOOD], send=Recorder(fail=True))
    assert code == 1 and State(root).read_log()[0]["emailed"] == ""
    code, send = go(root, cfg, scope, [])
    assert code == 0 and [x["title"] for x in send.calls[0][3]] == [FLOOD.title]
    assert State(root).read_log()[0]["emailed"] == "2026-10-28"


def test_unjudged_paper_is_not_marked_seen(root, cfg, scope):
    code, send = go(root, cfg, scope, [FLOOD, EBIKE], jev=BrokenJev({"floods": 0.92}))
    assert code == 0
    assert "class 3 ebikes in california" not in State(root).seen()
    assert any("could not judge 1 paper" in f for f in send.calls[0][5])


def test_zotero_failure_is_retried(root, cfg, scope):
    go(root, cfg, scope, [FLOOD], zot=lambda *a: "failed: HTTP 500")
    assert State(root).read_log()[0]["zotero"] == "failed: HTTP 500"
    go(root, cfg, scope, [], zot=lambda *a: "exists")
    assert State(root).read_log()[0]["zotero"] == "exists"


def test_all_sources_failing_needs_attention(root, cfg, scope):
    code, send = go(root, cfg, scope, [], failures=["Journal A: HTTP 403"])
    assert code == 1 and send.calls[0][5] == ["Journal A: HTTP 403"]


def test_dry_run_needs_no_keys_and_writes_nothing(root, cfg, scope):
    assert run(root, cfg, scope, dry_run=True, env={}, fetch=lambda c, k: ([FLOOD], [])) == 0
    assert not (root / "paper_log.csv").exists() and not (root / "state").exists()


def test_digest_quotes_evidence_and_escapes(cfg, scope, monkeypatch):
    monkeypatch.setattr("paperround.digest.open_access_pdf", lambda cfg, doi: None)
    row = {"title": "Floods <b>&</b> rain", "authors": "A. Author", "source": "J", "link": "https://doi.org/10.1/f",
           "doi": "10.1/f", "strands": "floods", "probability": "0.9", "evidence": "Floods follow droughts."}
    html = build_html(cfg, scope, [row], 40, ["Journal B: HTTP 403"])
    assert "Floods &lt;b&gt;&amp;&lt;/b&gt; rain" in html and "&ldquo;Floods follow droughts.&rdquo;" in html
    assert "Flood forecasting" in html and "Journal B: HTTP 403" in html and "1 new paper for you" in html
    assert subject(cfg, 0, []) == "Morning there! Nothing new in today's round"
    assert subject(cfg, 2, ["x"]).endswith("2 papers in today's round (with problems)")


def test_elsevier_abstracts_filled_for_new_papers_only_when_key_set(root, cfg, scope):
    bare = Paper("Flood forecasts without abstract", "https://doi.org/10.1016/j.x", "J Hydrol", doi="10.1016/j.x")
    calls = []

    def fill(papers, key):
        calls.append((key, [p.title for p in papers]))
        for p in papers:
            p.abstract = ABSTRACT
        return len(papers)

    run(root, cfg, scope, env={**ENV, "ELSEVIER_API_KEY": "e"}, today="2026-10-28", fetch=lambda c, k: ([bare], []),
        fill_abstracts=fill, jev=TitleJev({"floods": 0.92}), add_to_zotero=lambda *a: "added:K",
        send_email=Recorder())
    assert calls == [("e", [bare.title])] and State(root).read_log()[0]["evidence"] in ABSTRACT
    run(root, cfg, scope, env=ENV, today="2026-10-28", fetch=lambda c, k: ([], []), fill_abstracts=fill,
        jev=TitleJev({}), add_to_zotero=lambda *a: "x", send_email=Recorder())
    assert len(calls) == 1
