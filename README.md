<div align="center">
<img src="assets/clawd.png" alt="Clawd delivering the paper round" width="320">
<h1>Paper Round</h1>
<p><em>One email each morning with the new journal papers that match your research.</em></p>
</div>

Journal alerts bury the two papers you need under two hundred you don't. Paper Round reads every new paper in the
journals and searches you choose, keeps the ones that fit your research, and emails them to you each morning, each
with a sentence from its abstract showing why it was kept. Kept papers can also go straight into a Zotero collection
with full metadata and an open-access PDF link.

Built for my own PhD on subseasonal forecasting and compound climate extremes ([Lainey Ward](https://github.com/LaineyLouiseWard)),
written so anyone can run their own copy.

## How it works

Every morning a GitHub Actions job in your own private repo runs `paperround run`:

1. **Fetch** new papers from journal RSS feeds, Crossref (for journals that block feed readers), OpenAlex (by journal or
   by keyword across all journals) and arXiv.
2. **Drop** papers seen before, by DOI, arXiv id or title.
3. **Find abstracts** that feeds leave out, by DOI. A paper still without one waits up to a week for it.
4. **Judge** each paper with [Jev](https://typesafe.ai), which answers yes/no questions about text with a probability.
   You describe your research as a few strands in `scope.yaml`; each strand is one question, with optional exclusion
   questions. Code keeps a paper when a strand passes its threshold and none of its exclusions do.
5. **Quote** the abstract sentence that best shows the strand. The model never writes text, so nothing in the email can
   be made up.
6. **Add** kept papers to Zotero and **email** the digest through Resend.
7. **Save** state back to the repo as plain text: what has been seen, every paper's probabilities, and the log of kept
   papers.

## Setup

You need a GitHub account and keys for Jev ([typesafe.ai](https://typesafe.ai)) and Resend ([resend.com](https://resend.com),
free tier). Zotero and OpenAlex keys are optional.

```bash
pip install "paper-round @ git+https://github.com/LaineyLouiseWard/paper-round@v2.0.0"
mkdir my-paper-round && cd my-paper-round && git init
paperround init        # writes config.yaml, scope.yaml and .github/workflows/paper-round.yml
```

1. Edit `config.yaml` (journals, email, Zotero) and `scope.yaml` (your strands). The starter files explain each setting.
2. Copy `.env.example` from this repo to `.env`, add your keys, and try it locally: `paperround run --dry-run` lists
   what would be judged (no keys needed); `paperround run --no-zotero` does a full round.
3. Push to a **private** GitHub repo and add the keys as repository secrets (Settings → Secrets and variables →
   Actions): `TYPESAFE_API_KEY`, `RESEND_API_KEY`, and optionally `ZOTERO_API_KEY`, `OPENALEX_API_KEY`,
   `ELSEVIER_API_KEY`.
4. Run it once from the Actions tab. After that it runs every morning at 05:00 UTC.

## Cost and privacy

- **Jev** costs about $0.04 per million input tokens. A day of around 70 new papers uses roughly 300,000, so about a
  cent a day.
- **GitHub Actions** is free within the monthly minutes of a private repo; a round takes a minute or two.
- Your `scope.yaml` and log stay in your private repo. Each round sends your strand questions and the papers' titles
  and abstracts to TypeSafe to be judged; TypeSafe's legal terms commit to not training on user data.

## Tuning

- **"This wasn't relevant":** sharpen that strand's `yes`/`no` descriptions, add an exclusion question, or raise its
  threshold. One idea per question works best.
- **"It missed a paper":** check the journal is fetched (`--dry-run`), widen the strand, or add a strand.
- Every paper's probabilities are in `state/judgements.jsonl`, so a new threshold can be tried against past rounds
  without asking Jev again. `paperround judge papers.jsonl` scores a file of papers you already know about.

## Structure

| Path | Contents |
|---|---|
| `paperround/` | The package: `sources.py` fetching, `judge.py` the keep rule, `run.py` one round, `digest.py` the email |
| `paperround/starter/` | The files `paperround init` writes |
| `tests/` | `pytest` suite, run on every push |

## Licence

MIT. See [LICENSE](LICENSE).
