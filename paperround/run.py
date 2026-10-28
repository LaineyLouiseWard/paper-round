"""One round: fetch, drop papers already seen, judge, add to Zotero, email, save state.

State is written once, at the end. Papers Jev could not judge are left unseen, so tomorrow's round tries them again;
kept papers not yet added or emailed are picked up by the next round.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from . import digest, sources, zotero
from .config import Scope, Settings
from .judge import Jev, judge
from .papers import drop_seen
from .state import State

WAIT_DAYS = 7  # how long a paper without an abstract waits for one before it is judged on its title
FORGET_DAYS = 30  # a held paper that has left every feed by then is dropped from the waiting list


def require(env, name: str) -> str:
    if not env.get(name):
        raise SystemExit(f"{name} is not set (a GitHub secret, or a line in .env for local runs)")
    return env[name]


def run(root: Path, cfg: Settings, scope: Scope, *, dry_run=False, use_zotero=True, use_email=True, today=None,
        env=os.environ, fetch=sources.fetch_all, fill_abstracts=sources.fill_abstracts, jev=None,
        add_to_zotero=zotero.add, send_email=digest.send) -> int:
    """Returns 0, or 1 when the round needs attention (no email sent, or nothing could be fetched or judged)."""
    today = today or date.today().isoformat()
    state = State(root)
    if not dry_run:
        jev = jev or Jev(require(env, "TYPESAFE_API_KEY"), cfg.model)
        resend_key = require(env, "RESEND_API_KEY") if use_email else None

    print("Fetching")
    papers, failures = fetch(cfg, env.get("OPENALEX_API_KEY"))
    fetch_failed = bool(failures) and not papers
    new = drop_seen(papers, state.seen())
    print(f"{len(papers)} fetched, {len(new)} new")
    print(f"Abstracts found by DOI: {fill_abstracts(cfg, new, env.get('OPENALEX_API_KEY'), env.get('ELSEVIER_API_KEY'))}")
    waiting = state.waiting()
    cutoff = (date.fromisoformat(today) - timedelta(days=WAIT_DAYS)).isoformat()
    ready, held = [], []
    for p in new:
        first = waiting.get(p.key())
        if p.has_abstract() or not p.doi or (first and first <= cutoff):
            ready.append(p)
        else:
            held.append(p)
            waiting.setdefault(p.key(), today)
    if held:
        print(f"Waiting for an abstract: {len(held)}")
    if dry_run:
        for p in new:
            print(f"  [{p.source}] {p.title}{'' if p.has_abstract() else '  (no abstract)'}")
        return 0

    def attempt(paper):
        try:
            return judge(jev, paper, scope)
        except Exception as e:  # one bad answer must not sink the round; the paper is retried tomorrow
            return e

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(attempt, ready))

    rows, judged, records, errors = state.read_log(), [], [], []
    for p, res in zip(ready, results):
        if isinstance(res, Exception):
            errors.append(res)
            continue
        judged.append(p)
        records.append({"date": today, "title": p.title, "link": p.link, "doi": p.doi, "source": p.source,
                        "model": res.model, "probs": res.probs, "kept": res.kept, "evidence": res.evidence})
        if res.kept:
            rows.append({"date": today, "title": p.title, "authors": p.authors, "source": p.source, "link": p.link,
                         "doi": p.doi or "", "strands": ";".join(res.kept),
                         "probability": f"{res.probs[res.kept[0]]:.2f}", "evidence": res.evidence,
                         "zotero": "", "emailed": ""})
    n_kept = sum(1 for r in records if r["kept"])
    print(f"Judged {len(judged)}, kept {n_kept}, could not judge {len(errors)}")
    if errors:
        failures.append(f"Jev could not judge {len(errors)} paper(s); they will be tried again tomorrow "
                        f"(first error: {errors[0]})")

    zotero_key = env.get("ZOTERO_API_KEY")
    if use_zotero and zotero_key and cfg.zotero_library_id:
        for r in rows:
            if r["zotero"] == "" or r["zotero"].startswith("failed"):
                r["zotero"] = add_to_zotero(cfg, zotero_key, r, [scope.label(s) for s in r["strands"].split(";")])
                if r["zotero"].startswith("failed"):
                    failures.append(f"Zotero, {r['title'][:60]}: {r['zotero']}")

    email_sent = True
    pending = [r for r in rows if r["emailed"] == ""]
    if use_email and (pending or cfg.send_when_empty):
        try:
            send_email(cfg, resend_key, scope, pending, len(new), failures)
            for r in pending:
                r["emailed"] = today
        except Exception as e:
            email_sent = False
            failures.append(f"Email: {e}")

    state.write_log(rows)
    state.add_seen(judged)
    state.add_judgements(records)
    done, forget = {p.key() for p in judged}, (date.fromisoformat(today) - timedelta(days=FORGET_DAYS)).isoformat()
    state.write_waiting({k: d for k, d in waiting.items() if k not in done and d > forget})
    for f in failures:
        print(f"PROBLEM: {f}")
    return 1 if (not email_sent or fetch_failed or (ready and not judged)) else 0
