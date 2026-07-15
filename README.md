<div align="center">
<img src="assets/clawd.png" alt="Clawd delivering the paper round" width="360">
<h1>Paper Round</h1>
<p>
<a href="https://claude.com/product/claude-code"><img src="https://img.shields.io/badge/powered_by-Claude_Code-D97757?logo=claude&logoColor=white" alt="powered by Claude Code"></a>
<a href="https://github.com/LaineyLouiseWard/paper-round"><img src="https://img.shields.io/badge/status-active-brightgreen" alt="status"></a>
<a href="https://github.com/LaineyLouiseWard/paper-round/stargazers"><img src="https://img.shields.io/github/stars/LaineyLouiseWard/paper-round" alt="stars"></a>
<a href="https://github.com/LaineyLouiseWard/paper-round/issues"><img src="https://img.shields.io/github/issues/LaineyLouiseWard/paper-round" alt="issues"></a>
<a href="LICENSE"><img src="https://img.shields.io/github/license/LaineyLouiseWard/paper-round" alt="license"></a>
</p>
<p><em>Your daily paper round, except it delivers journal papers straight to your inbox.</em></p>
</div>

Every morning, a scheduled Claude agent reads the feeds of the journals
*you* follow, scores each new paper against *your* written research scope,
**emails you the relevant ones**, and files them into **Zotero** with full
metadata and open-access PDF links.

**No server. No GitHub Actions. No LLM API key.** A claude.ai Pro/Max
subscription is the engine. Adapted from the workflow I built for my own
PhD ([Lainey Ward](https://github.com/LaineyLouiseWard)).

![Example daily digest](assets/digest.png)

## 🚀 Start here

**Fastest path (recommended):** click **[Use this template](https://github.com/LaineyLouiseWard/paper-round/generate)**,
open your new repo in Claude Code, and paste this one prompt. *Claude
does the setup with you, conversationally:*

```text
Set up Paper Round (this repo) for me.
1. Read README.md, source_list.md, research_scope.md, relevance_rules.md,
   config.yaml and .env.example.
2. Interview me: which journals I follow (build source_list.md entries
   using the publisher patterns in that file, with Crossref or OpenAlex
   fallbacks where RSS is blocked), my email address, and my Zotero
   library details if I use it.
3. Ask me to paste my thesis or proposal abstract, and to export my
   Zotero library into this folder (File > Export Library > CSV) if I
   have one. Draft research_scope.md and relevance_rules.md from both,
   keeping the scaffolds' structure. Fill in config.yaml.
4. Help me create .env from .env.example, telling me exactly where each
   key comes from (the Keys table in README.md).
5. Run: pip install -r requirements.txt && python screen.py --dry-run
   and fix anything that fails.
6. Fill the placeholders in routine_prompt.md, then walk me through the
   cloud steps from the README (GitHub App access, network allowlist,
   creating the routine with /schedule) one at a time, waiting for me to
   confirm each before moving on.
```

<details>
<summary><b>Prefer to set up by hand?</b> The same six steps, manually</summary>

1. Click **Use this template** to create your own repo (private is fine)
2. Edit `source_list.md` (your journals) and `config.yaml` (your settings)
3. Draft your scope files, see [Writing your scope and rules](#%EF%B8%8F-writing-your-scope-and-rules)
4. `cp .env.example .env` and add your keys: [resend.com](https://resend.com) (required), [zotero.org/settings/keys](https://www.zotero.org/settings/keys) and [openalex.org](https://openalex.org) (optional)
5. `pip install -r requirements.txt && python screen.py --dry-run` (Python 3.10+)
6. Set up the [cloud routine](#%EF%B8%8F-schedule-the-cloud-routine) and fire a test run

</details>

## ⚙️ How it works

![How Paper Round works](assets/pipeline.png)

- **Python does the data work**: fetching feeds (with Crossref and
  OpenAlex fallbacks for publishers that block RSS), dedup by title and
  DOI, logging to a committed CSV, and filing into Zotero.
- **Claude does exactly one thing**: judge each new paper against
  `research_scope.md` and `relevance_rules.md`.
- **Failures are loud, never invented.** The routine's integrity rules pin
  every claimed paper to the fetched data, because a screening agent whose
  fetch fails will otherwise *invent plausible papers* — the first live
  run of this pipeline produced seven fabricated papers with DOIs that
  resolved to 404 pages. Under the rules, "0 new papers" is a successful
  outcome and any failure is quoted verbatim in the digest.

## ✍️ Writing your scope and rules

`research_scope.md` and `relevance_rules.md` *are* the screening prompt.
Don't write them from scratch — give Claude Code your research taste:

- **Paste your abstract** (thesis, proposal, or a recent paper), *and*
- **Export your Zotero library** into the folder (File → Export Library →
  CSV). The library shows your taste, the abstract shows where you're
  heading; together they draft well. Claude can also suggest
  `source_list.md` entries from the journals that dominate your library.

Then treat the **first two weeks as calibration**: every false positive
becomes an exclusion, every missed paper becomes a trigger. The exclusion
list does most of the filtering work, so grow it freely.

## ☁️ Schedule the cloud routine

Each morning a Claude Code cloud agent clones this repo, runs the
pipeline, and emails you. A push notification states the outcome either
way, so *a failed run announces itself*. Runs draw on your normal plan
usage — a few minutes of the cheapest model per day.

Each step below guards against a real failure mode:

1. **Grant GitHub access.** The cloud agent clones via the Claude GitHub
   App, not your local credentials. Configure it at
   [github.com/settings/installations](https://github.com/settings/installations)
   → **Claude** → grant access to this repo.
2. **Open network access.** Cloud environments block unknown domains by
   default. In [claude.ai/code](https://claude.ai/code), open your
   environment's settings → Network access → **Custom**, keep the default
   package list, and add your feed domains plus `api.crossref.org`,
   `api.unpaywall.org`, `api.zotero.org`, `api.resend.com`,
   `api.openalex.org`, `export.arxiv.org`, `arxiv.org`, `doi.org`.
3. **Create the routine.** Fill in the placeholders in
   `routine_prompt.md`, then ask Claude Code (`/schedule`, *"run this
   prompt daily at 6am against my repo"*) or use
   [claude.ai/code/routines](https://claude.ai/code/routines). Cheapest
   model tier; cron times are UTC.
4. **Fire a manual test run** and read the push notification: it states
   `Digest EMAILED …`, `Resend FAILED …`, or `Email FAILED …` with the
   digest preserved. *Check the commit, your Zotero inbox, and the email
   before trusting it.*

## 🔑 Keys

All optional except Resend. They go in `.env` locally and in the routine
prompt (or environment variables) in the cloud — **never commit them**.

| Key | Where to get it | Needed for |
| --- | --- | --- |
| `RESEND_API_KEY` | free account at [resend.com](https://resend.com) | **the emailed digest.** Without a verified domain, send from `onboarding@resend.dev` (delivers only to your own Resend account email) |
| `ZOTERO_API_KEY` | [zotero.org/settings/keys](https://www.zotero.org/settings/keys), write access | filing papers into your library. *Leave empty to skip Zotero and curate from the email* |
| `OPENALEX_API_KEY` | free from [openalex.org](https://openalex.org) | only if `config.yaml` lists `openalex_sources` (journals with no workable RSS) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | local screening runs only; *the cloud routine screens natively* |

## 📁 Project structure

Everything sits at the repo root: each file is either the pipeline or a
file you edit.

| File | Purpose |
| ---- | ------- |
| `screen.py` | Pipeline: fetch, dedup, screen, log, Zotero. **No editing needed** |
| `config.yaml` | All your settings: email, Zotero library, sources, model |
| `.env.example` | Template for `.env`, where keys live (gitignored) |
| `source_list.md` | Your feeds, with working URL patterns per publisher |
| `research_scope.md` | Your research context, half of the screening prompt |
| `relevance_rules.md` | The 0 to 4 scoring rules, the other half |
| `routine_prompt.md` | The cloud routine's task prompt, with placeholders |
| `paper_log.csv` | Papers scoring ≥ 3 (auto-generated, committed daily) |
| `seen_papers.txt` | Titles and DOIs already screened (auto-generated) |

## 🛠️ Troubleshooting

If the four setup steps are done, none of these should fire. When one
does anyway:

<details>
<summary><b>Expand the failure table</b></summary>

| Symptom | Cause | Fix |
| --- | --- | --- |
| Routine disabled itself, "init failed" | Claude GitHub App can't clone the (private) repo | Grant repo access at [github.com/settings/installations](https://github.com/settings/installations) |
| Run reports network/proxy errors | Environment allowlist blocks feeds/APIs | Environment settings → Network access → Custom → add the domains from step 2 |
| Digest never arrives | Resend missing from the allowlist, unverified from-address, or the free tier's own-address restriction | The push notification states the outcome verbatim; check `api.resend.com` is allowlisted and the from/to pairing matches your Resend tier |
| Expecting email from a Gmail connector | Google's Gmail connector has no send tool | It can only create drafts; that's why this uses Resend |
| Digest lists papers that don't exist | Fetch failed and the model improvised | Keep the integrity rules block; spot-check DOIs |
| First run finds hundreds of papers | Full feed contents hit an empty `seen_papers.txt` | Expected one-off backlog flush; daily volume after that is a handful |

</details>

## ❓ FAQ

**What does it cost to run?** It draws on your Claude Pro/Max plan's
included usage: a few minutes of the cheapest model per day. *No separate
bill, no per-token API charges.*

**Will it hallucinate papers?** That's what the integrity rules are for:
every paper must appear verbatim in the fetched feed data, and failures
get reported instead of papered over. Spot-check a DOI occasionally
anyway — trust, but verify.

**Does it get me past paywalls?** No. Cards link the paper's page, plus
an open-access PDF whenever [Unpaywall](https://unpaywall.org/) knows one.

**Can I use it without Zotero?** Yes — leave `ZOTERO_API_KEY` empty and
curate from the email instead.

**Can I run it without the cloud routine?** Yes: `python screen.py`
locally with an `ANTHROPIC_API_KEY`, scheduled however you like. The
cloud routine is just the zero-infrastructure way.

## 🤝 Contributing

Issues and pull requests welcome — especially working feed patterns for
more publishers and example scope files from other fields.

## ❤️ Acknowledgements

Ideas borrowed from tools that solve this for arXiv-centric workflows:

- [zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily)
- [ArxivDigest](https://github.com/AutoLLM/ArxivDigest)
- [paperzorro](https://github.com/Rafael-Silva-Oliveira/paperzorro)

Running on freely provided scholarly infrastructure:

- [Crossref](https://www.crossref.org/) — bibliographic metadata
- [OpenAlex](https://openalex.org/) — open catalogue of research
- [Unpaywall](https://unpaywall.org/) — open-access PDF discovery
- [Zotero](https://www.zotero.org/) — reference management
- [arXiv](https://arxiv.org/) — preprints

## 📃 Licence

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
