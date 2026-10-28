# Tuning this Paper Round

This repo runs Paper Round every morning on GitHub Actions. The user will ask you to change what it keeps.

## Files

- `scope.yaml`: the strands. Each strand is a yes/no question that Jev answers from a paper's title and abstract,
  with `yes` and `no` descriptions, a `threshold`, and optional `exclude` questions. A paper is kept when a strand's
  probability reaches its threshold and none of that strand's exclusions reaches `exclude_threshold`.
- `config.yaml`: journals, keyword searches, Zotero and email.
- `state/judgements.jsonl`: one line per judged paper, with its title, DOI, `probs` (keyed by strand id and by
  `strand/exclusion` id), `kept` and the quoted `evidence`.
- `paper_log.csv`: the kept papers. `state/seen.txt`: everything already judged.

## "This paper shouldn't have come through"

1. Find the paper in `state/judgements.jsonl` and read its probabilities.
2. Make the smallest change that fixes it. If it scored just above the threshold, raise the threshold. If it belongs to
   a kind of paper the user never wants, add an exclusion question that names that kind. Otherwise sharpen the
   strand's `no` description.
3. For a threshold change, use `state/judgements.jsonl` to list the past kept papers it would drop, and show the user
   before saving.

## "It missed this paper"

1. If the paper is not in `state/judgements.jsonl` or `state/seen.txt`, it was never fetched: add its journal to
   `config.yaml` and confirm with `paperround run --dry-run`.
2. If it was judged, read its probabilities: lower the threshold, widen `yes`, or add a strand for an idea the scope
   does not cover yet.

## Testing a wording change

Old probabilities do not apply once a question's wording changes. Write the papers in question (title and abstract)
to a `.jsonl` file, including a few that should stay kept, and run `paperround judge file.jsonl` (needs
`TYPESAFE_API_KEY` in `.env`).

## Rules

- One idea per question. A second idea is a new strand; a "but not ..." case is an exclusion with its own question.
- Keys never go in files: they are GitHub secrets, or `.env` locally (gitignored).
- Commit and push `scope.yaml` so the next morning's round uses it.
