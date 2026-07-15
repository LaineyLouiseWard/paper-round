<div align="center">
<img src="assets/logo.png" alt="Paper Round logo" width="190">
<h1>Paper Round</h1>
<p>
<a href="https://github.com/LaineyLouiseWard/paper-round"><img src="https://img.shields.io/badge/status-active-brightgreen" alt="status"></a>
<a href="https://github.com/LaineyLouiseWard/paper-round/stargazers"><img src="https://img.shields.io/github/stars/LaineyLouiseWard/paper-round" alt="stars"></a>
<a href="https://github.com/LaineyLouiseWard/paper-round/issues"><img src="https://img.shields.io/github/issues/LaineyLouiseWard/paper-round" alt="issues"></a>
<a href="LICENSE"><img src="https://img.shields.io/github/license/LaineyLouiseWard/paper-round" alt="license"></a>
</p>
<p><em>Your daily paper round, except it delivers journal papers.</em></p>
</div>

A scheduled Claude agent reads your journals' feeds every morning, scores
each new paper against your written research scope, emails you a digest,
and files the keepers into Zotero with full metadata and open-access PDF
links. One short email instead of eleven tables of contents. Adapted from
the workflow I built for my own PhD
([Lainey Ward](https://github.com/LaineyLouiseWard)).

No server, no GitHub Actions, no LLM API key: a claude.ai Pro/Max
subscription is the engine. Unlike arXiv-centric recommenders it watches
the peer-reviewed journals of your field across publishers, and every
paper in the digest is traceable to a feed the code actually fetched.

![Example daily digest](assets/digest-example.png)

Titles link to the paper on the journal's site; the PDF link appears when
an open-access copy exists. Score-4 papers come first.

## Quick start

1. Click **Use this template** to create your own repo (private is fine)
2. Edit `source_list.md` (your journals) and `config.yaml` (your settings)
3. Draft your scope files: see [Writing your scope and rules](#writing-your-scope-and-rules)
4. `cp .env.example .env` and fill in [the keys you use](#keys)
5. `pip install -r requirements.txt && python screen.py --dry-run` (Python 3.10+)
6. Set up the [cloud routine](#schedule-the-cloud-routine) and fire a test run

## How it works

Deterministic Python does the data work: fetching feeds (with Crossref
and OpenAlex fallbacks for publishers that block RSS), dedup by title and
DOI, logging to a committed CSV, and filing into Zotero with Crossref
metadata and Unpaywall PDF links. Claude does exactly one thing: judge
each new paper against `research_scope.md` and `relevance_rules.md`.

The routine prompt opens with integrity rules that pin every claimed
paper to the fetched data. They exist because a screening agent whose
fetch step fails will invent plausible papers rather than admit failure;
the first live run of this pipeline produced seven fabricated papers with
DOIs that resolved to 404 pages. Under the rules, "0 new papers" is an
explicitly successful outcome and any failure is quoted verbatim in the
digest. Spot-check a DOI from your digest now and then anyway.

## Writing your scope and rules

`research_scope.md` and `relevance_rules.md` *are* the screening prompt.
Don't write them from scratch. Open your copy in Claude Code, paste your
thesis or proposal abstract, drop an export of your Zotero library beside
it (File → Export Library → CSV), and ask it to draft both files plus
suggested `source_list.md` entries from the journals that dominate your
library. An abstract alone is too thin: the library shows your taste, the
abstract shows where you're heading, and together they draft well.
Correct what it gets wrong.

Treat the first two weeks of digests as calibration: every false positive
becomes an exclusion, every paper you spot elsewhere that the monitor
missed becomes a trigger. The exclusion list does most of the filtering
work, so grow it freely.

## Schedule the cloud routine

Each morning a Claude Code cloud agent clones this repo, runs the
pipeline, and emails you; a push notification states the outcome either
way, so a failed run announces itself. Runs draw on your normal plan
usage, a few minutes of the cheapest model per day.

Each setup step below guards against a real failure mode. Skipping one
gives you a silently dead (or worse, silently lying) monitor:

1. **GitHub access.** The cloud agent clones via the Claude GitHub App,
   not your local credentials. Install it via github.com → Settings →
   Applications → Installed GitHub Apps → Claude → Configure, and grant
   access to this repo. Without access to a private repo, every run dies
   at init and the routine disables itself.
2. **Network access.** Cloud environments block unknown domains by
   default. In claude.ai/code open your environment's settings → Network
   access → **Custom**, keep the default package-manager list, and add
   your feed domains plus `api.crossref.org`, `api.unpaywall.org`,
   `api.zotero.org`, `api.resend.com`, `api.openalex.org`,
   `export.arxiv.org`, `arxiv.org`, and `doi.org`.
3. **Create the routine.** Fill in the placeholders in
   `routine_prompt.md`, then either ask Claude Code (`/schedule`, "run
   this prompt daily at 6am against my repo") or use
   claude.ai/code/routines. Attach your repo, pick the cheapest model
   tier, set the cron (times are UTC).
4. **Fire a manual test run** and read the push notification: it states
   `Digest EMAILED …`, `Resend FAILED …`, or `Email FAILED …` with the
   digest preserved. Check the commit, your Zotero inbox, and the email
   before trusting it.

## Keys

All optional except Resend. They go in `.env` locally and in the routine
prompt (or environment variables) in the cloud; never commit them.

| Key | Where to get it | Needed for |
| --- | --- | --- |
| `RESEND_API_KEY` | free account at [resend.com](https://resend.com) | the emailed digest. Without a verified domain, send from `onboarding@resend.dev`, which only delivers to your own Resend account email |
| `ZOTERO_API_KEY` | [zotero.org/settings/keys](https://www.zotero.org/settings/keys), write access | filing papers into your library. Leave empty to skip Zotero and curate from the email |
| `OPENALEX_API_KEY` | free from [openalex.org](https://openalex.org) | only if `config.yaml` lists `openalex_sources` (journals with no workable RSS) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | local screening runs only; the cloud routine screens natively |

## Project structure

Everything sits at the repo root: each file is either the pipeline or a
file you edit, and `screen.py` finds its siblings by location.

| File | Purpose |
| ---- | ------- |
| `screen.py` | Pipeline: fetch, dedup, screen, log, Zotero. No editing needed |
| `config.yaml` | All your settings: email, Zotero library, sources, model |
| `.env.example` | Template for `.env`, where keys live (gitignored) |
| `source_list.md` | Your feeds, with working URL patterns per publisher |
| `research_scope.md` | Your research context, half of the screening prompt |
| `relevance_rules.md` | The 0 to 4 scoring rules, the other half |
| `routine_prompt.md` | The cloud routine's task prompt, with placeholders |
| `paper_log.csv` | Papers scoring ≥ 3 (auto-generated, committed daily) |
| `seen_papers.txt` | Titles and DOIs already screened (auto-generated) |

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Routine disabled itself, "init failed" | Claude GitHub App can't clone the (private) repo | Grant repo access: github.com → Settings → Applications → Claude → Configure |
| Run reports network/proxy errors | Environment allowlist blocks feeds/APIs | Environment settings → Network access → Custom → add the domains from step 2 |
| Digest never arrives | Resend missing from the allowlist, unverified from-address, or the free tier's own-address restriction | The push notification states the outcome verbatim; check `api.resend.com` is allowlisted and the from/to pairing matches your Resend tier |
| Expecting email from a Gmail connector | Google's Gmail connector has no send tool | It can only create drafts; that's why this uses Resend |
| Digest lists papers that don't exist | Fetch failed and the model improvised | Keep the integrity rules block; spot-check DOIs |
| First run finds hundreds of papers | Full feed contents hit an empty `seen_papers.txt` | Expected one-off backlog flush; daily volume after that is a handful |

## Acknowledgements

Ideas borrowed from
[zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily),
[ArxivDigest](https://github.com/AutoLLM/ArxivDigest) and
[paperzorro](https://github.com/Rafael-Silva-Oliveira/paperzorro), which
solve the same problem for arXiv-centric workflows. The pipeline runs on
freely provided services: journal RSS feeds, the
[Crossref](https://www.crossref.org/), [OpenAlex](https://openalex.org/),
[Unpaywall](https://unpaywall.org/) and [Zotero](https://www.zotero.org/)
APIs, and [arXiv](https://arxiv.org/).

## Licence

MIT, see [LICENSE](LICENSE).
