# Relevance Rules

Instructions for scoring papers during screening. Applied to title +
abstract only. Keep the 0–4 scale and the exclusions-first procedure; edit
the trigger lists to match your scope.

---

## Scoring scale

| Score | Label | Definition |
|-------|-------|------------|
| 0 | Irrelevant | No connection to any core strand, or falls under an exclusion topic. |
| 1 | Tangential | Touches a relevant domain but not your questions, scales, or methods. |
| 2 | Possibly useful | Addresses a relevant topic peripherally. Background at best. |
| 3 | Relevant | Directly addresses at least one strand with clear methodological or conceptual overlap. Worth reading. |
| 4 | Highly relevant | Addresses the core question or bridges two or more strands. Likely to inform a chapter, method, or gap argument. Priority read. |

**Save threshold: score >= 3.** Papers scoring 0–2 are discarded.

---

## Score 4 triggers (any one is sufficient)

Write the handful of paper descriptions that would make you drop what you're
doing and read. Be specific — these define your "priority read" pile.

- (e.g. your exact phenomenon studied at your exact timescale)
- (e.g. a new method for the thing your methods chapter does)

## Score 3 triggers (any one is sufficient)

Broader but still clearly on-topic. One trigger per strand works well.

- (strand 1, stated broadly)
- (strand 2, stated broadly)
- (methods you use, applied anywhere in your field)

## Automatic exclusions (score 0, do not evaluate further)

The topics that pattern-match your keywords but never turn out useful.
This list does most of the noise filtering — grow it as false positives
appear in your digests.

- (e.g. adjacent subfield you don't follow)
- (e.g. a timescale or system out of scope)

---

## Scoring procedure

1. Check exclusions first — if any match, assign 0 and stop.
2. Check score-4 triggers — if any match, assign 4.
3. Check score-3 triggers — if any match, assign 3.
4. Otherwise judge tangential (1) vs possibly useful (2) from proximity to
   the strands in `research_scope.md`.

## Output fields per saved paper

| Field | Description |
|-------|-------------|
| date | Date screened |
| title | Paper title |
| source | Feed / journal name |
| link | URL to paper |
| relevance_score | 3 or 4 |
| relevance_summary | 1–2 sentence reason for the score |
| topic_labels | Comma-separated labels from a fixed vocabulary you define (e.g. one label per strand plus a few method tags) |
