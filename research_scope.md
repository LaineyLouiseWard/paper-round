# Research Scope

This file, together with `relevance_rules.md`, is the screening prompt. The
model reads both before scoring each paper, so write them the way you would
brief a new research assistant: enough context to judge relevance from a
title and abstract, no more.

Replace everything below with your own scope.

---

## Research context

One or two paragraphs on what your research is about: the field, the central
question, the methods you use, and the setting (PhD thesis, lab programme,
review project). Name the concepts a relevant paper would mention.

## Core strands

List the distinct threads of your work — screening decisions get sharper when
the model can ask "which strand does this touch?" rather than "is this
vaguely related?". For example:

1. **Strand one** — e.g. a prediction or modelling problem at a specific scale
2. **Strand two** — e.g. a class of events or phenomena you study
3. **Strand three** — e.g. a methodological thread (verification, ML, indices)

## Adjacent but out of scope

Topics that sound close but that you deliberately do not follow — naming
these here prevents most false positives. Pair this with the automatic
exclusions in `relevance_rules.md`.
