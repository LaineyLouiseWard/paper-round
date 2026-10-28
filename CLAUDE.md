# Paper Round

A daily email of new journal papers that match the user's research. `paperround run` fetches feeds, drops papers
already seen, asks Jev (TypeSafe) yes/no questions about each new paper, keeps those that pass, adds them to Zotero,
emails a digest, and saves state. GitHub Actions runs it each morning in the user's own private repo.

## Layout

- `paperround/`: the code. `judge.py` holds the keep rule; `run.py` the order of a round; `starter/` the files
  `paperround init` writes into a user's repo.
- A user's repo holds `config.yaml` (sources, Zotero, email), `scope.yaml` (research strands), `state/`,
  `paper_log.csv` and `.github/workflows/paper-round.yml`. Keys are GitHub secrets or a local `.env`, never in files.

## Rules

- Jev only answers questions; code decides. Never add a step where a model writes text that reaches the email or the
  log: the "why" line is a sentence copied from the abstract.
- Tuning relevance means editing `scope.yaml`: a strand's `yes`/`no` descriptions, its threshold, or an exclusion
  question. One idea per question. Thresholds can be re-tested offline from `state/judgements.jsonl`.
- Adding a journal: try its RSS pattern (listed in `starter/config.yaml`); AMS needs `crossref_issn`; journals without
  working RSS go under `openalex`. A journal counts as added when `paperround run --dry-run` lists papers from it.
- Run `pytest` after any code change. The keep rule, the quote step and the answer check are mutation-tested: keep
  their tests failing when the guarded behaviour breaks.
