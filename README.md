# Literature Monitor Template

A daily AI literature monitor: a scheduled Claude agent screens the RSS
feeds of your chosen journals against your written research scope, emails
you a digest of relevant papers, files them into your Zotero library with
full metadata and open-access PDF links, and commits an auditable log to
this repo. You read one short email a day instead of eleven tables of
contents.

## Broader context

Built from a working setup used for a PhD literature review. The design
principle is a strict division of labour: deterministic Python does the
data acquisition (feeds, dedup, Zotero, logging) and the model does only
the judgment call (is this paper relevant to *this* scope?). Everything the
model claims must be traceable to what the code fetched — see
[Why the integrity rules exist](#why-the-integrity-rules-exist).

## Tech stack

| Category | Tools |
| -------- | ----- |
| Feed parsing | Feedparser; Crossref API fallback for bot-protected publishers; arXiv API |
| Screening | Claude (scheduled cloud routine — screens natively, no API key; or locally via the Anthropic API) |
| Metadata | Crossref API (full bibliographic data from DOI) |
| OA PDFs | Unpaywall API |
| Zotero | Zotero Web API via plain HTTP (deliberately not pyzotero — it fails to build in sandboxed cloud environments) |
| Email | Gmail connector attached to the cloud routine |
| Language | Python 3 |

## Getting started

### 1. Make it yours

1. Click **Use this template** on GitHub to create your own copy (private
   is fine — see step 3.1).
2. Edit `source_list.md` — replace the example feeds with your journals.
   The publisher-pattern table in that file shows how to find working feed
   URLs.
3. Edit `research_scope.md` and `relevance_rules.md` — these two files ARE
   the screening prompt. The rules file keeps a 0–4 scale with an
   exclusions-first procedure; you fill in the triggers.
4. Edit the config block at the top of `screen.py`: your contact email
   (sent to Crossref/Unpaywall), your Zotero library ID and inbox
   collection key, optional arXiv search terms, and Crossref fallbacks for
   any AMS journals.

### 2. Test locally

```bash
pip install -r requirements.txt

# Fetch + dedup only — verifies your feeds work, costs nothing
python screen.py --dry-run

# Full local run (screening via the Anthropic API)
export ANTHROPIC_API_KEY='sk-ant-...'
export ZOTERO_API_KEY='...'        # optional; skipped if unset
python screen.py
```

### 3. Schedule the cloud routine

The daily automation is a Claude Code cloud routine (claude.ai Pro/Max):
an agent in Anthropic's cloud clones this repo each morning, runs the
pipeline, and emails you. Runs draw on your normal plan usage — a few
minutes of the cheapest model per day, no separate charge.

Each of these steps guards against a real failure mode; skipping one gives
you a silently dead (or worse, silently lying) monitor:

1. **GitHub access.** The cloud agent clones via the Claude GitHub App —
   your local git credentials are irrelevant. Install/configure it at
   github.com → Settings → Applications → Installed GitHub Apps → Claude,
   and grant access to this repo. If the repo is private and the app lacks
   access, every run dies at session init and the routine auto-disables
   after a few failures.
2. **Network access.** Cloud environments default to an allowlist that
   blocks journal feeds and academic APIs. In claude.ai/code, open your
   environment's settings → Network access → **Custom**, keep the default
   package-manager list, and add your feed domains plus: `api.crossref.org`,
   `api.unpaywall.org`, `api.zotero.org`, `export.arxiv.org`, `arxiv.org`,
   `doi.org`.
3. **Gmail connector.** Connect Gmail at claude.ai/settings/connectors and
   approve **all** permission scopes. Note which Google account you sign in
   with — that's where drafts land if the connector offers no direct-send
   tool.
4. **Create the routine.** Take `routine_prompt.md`, fill in the
   placeholders, and create the routine — either ask Claude Code
   (`/schedule` — "run this prompt daily at 6am against my repo, with the
   Gmail connector") or use claude.ai/code/routines. Attach the Gmail
   connector and your repo, pick the cheapest model tier, and set the cron
   (note: cron times are UTC).
5. **Fire a manual test run** and read the push notification — the prompt
   makes the agent's final message state exactly what happened
   (`Digest EMAILED …` / `saved as DRAFT …` / `Gmail FAILED: <error>`).
   Don't assume the first run worked; check the commit, your Zotero inbox,
   and the email.

## Why the integrity rules exist

The routine prompt begins with a block of integrity rules. They were
written after a real incident: a run whose feed-fetch step failed produced
a confident digest of seven entirely fabricated papers — plausible titles,
real-looking DOIs that resolved to 404s or unrelated work. A screening
agent under failure does not say "I failed" unless told to; it fills the
gap. The rules pin every claimed paper to the fetched JSON, make "0 new
papers" an explicitly successful outcome, and require failures to be
reported with the exact error. Keep them, and spot-check a DOI from your
digest now and then.

## Project structure

| File | Purpose |
| ---- | ------- |
| `screen.py` | Pipeline: fetch, dedup, screen, log, Zotero upload. Config block at top. |
| `source_list.md` | Your feeds, with working URL patterns per publisher |
| `research_scope.md` | Your research context — half of the screening prompt |
| `relevance_rules.md` | 0–4 scoring rules — the other half |
| `routine_prompt.md` | The cloud routine's task prompt, with placeholders |
| `paper_log.csv` | Papers scoring ≥ 3 (auto-generated, committed daily) |
| `seen_papers.txt` | Normalised titles already screened (auto-generated) |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Routine disabled itself, "init failed" | Claude GitHub App can't clone the (private) repo | Grant repo access: github.com → Settings → Applications → Claude → Configure |
| Run reports network/proxy errors | Environment allowlist blocks feeds/APIs | Environment settings → Network access → Custom → add the domains from step 3.2 |
| Gmail calls fail with "insufficient authentication scopes" | Connector authorized without full permissions | Disconnect and reconnect Gmail, approving every scope |
| Digest never arrives | Wrong Google account on the connector, or draft-only connector | Check which account the connector uses; check its Drafts; read the run's push notification — it states the outcome |
| Digest lists papers that don't exist | Fetch failed and the model improvised | Keep the integrity rules block; spot-check DOIs; read the failure line in the email footer |
| First run finds hundreds of papers | Feeds' full current contents on an empty `seen_papers.txt` | Expected one-off backlog flush; daily volume is a handful |

## Data

- Feeds are fetched live each run; the only state is `seen_papers.txt`
  (dedup) and `paper_log.csv` (results), both committed back to the repo
  daily so the screening history is versioned and auditable.
- `ZOTERO_API_KEY` (create at zotero.org/settings/keys, write access to
  your target library) lives in the routine prompt or, better, in the cloud
  environment's variables — never commit it to the repo.
- `ANTHROPIC_API_KEY` is only needed for local runs; the cloud routine
  screens natively.

## Licence

MIT — see [LICENSE](LICENSE).
