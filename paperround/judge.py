"""Relevance by Jev (TypeSafe): yes/no probabilities per strand and exclusion; code makes the call.

Jev never writes text. The keep rule is ordinary code over its probabilities, and the line that explains a keep is a
sentence copied from the abstract, chosen by asking Jev about each sentence in turn.
"""

import re
import time
from dataclasses import dataclass, field

import requests

from .config import Scope, Strand
from .papers import Paper

JEV_URL = "https://api.typesafe.ai/v1/systemone"
MAX_SENTENCES = 15


class JevError(RuntimeError):
    pass


class Jev:
    def __init__(self, api_key: str, model: str = "jev-latest", session: requests.Session | None = None):
        self.api_key, self.model = api_key, model
        self.session = session or requests.Session()

    def ask(self, state: dict, questions: dict) -> tuple[dict[str, float], str]:
        """One request; returns {question id: probability of yes} and the model version that answered."""
        body = {"model": self.model, "state": state, "questions": questions}
        for attempt in range(4):
            resp = self.session.post(JEV_URL, json=body, timeout=60,
                                     headers={"Authorization": f"Bearer {self.api_key}"})
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            if not resp.ok:
                raise JevError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return read_answers(data, questions), data.get("model", self.model)
        raise JevError(f"HTTP {resp.status_code} after retries")


def read_answers(data: dict, questions: dict) -> dict[str, float]:
    """Every question answered with a probability in [0, 1], or JevError: nothing partial gets through."""
    answers = data.get("answers") or {}
    probs = {}
    for qid in questions:
        p = (answers.get(qid) or {}).get("noul")
        if not isinstance(p, (int, float)) or not 0 <= p <= 1:
            raise JevError(f"no valid answer for {qid!r}: {answers.get(qid)!r}")
        probs[qid] = float(p)
    return probs


def _noul(instructions: str, yes: str, no: str) -> dict:
    q = {"type": "noul", "instructions": instructions}
    if yes or no:
        q["criteria"] = {"true": yes, "false": no}
    return q


def paper_state(paper: Paper) -> dict:
    return {"paper": {"title": paper.title, "journal": paper.source,
                      "abstract": paper.abstract or "(no abstract in the feed; judge from the title)"}}


def relevance_questions(scope: Scope) -> dict:
    """One question per strand and one per exclusion, all asked in a single request."""
    qs = {}
    for s in scope.strands:
        qs[s.id] = _noul(f"Read `paper` (title and abstract). {s.question}", s.yes, s.no)
        for e in s.exclude:
            qs[f"{s.id}/{e.id}"] = _noul(f"Read `paper` (title and abstract). {e.question}", e.yes, e.no)
    return qs


def decide(probs: dict[str, float], scope: Scope) -> list[str]:
    """Strands the paper is kept for: its yes is at or above the strand's threshold and none of that strand's
    exclusions reaches the exclusion threshold. Ordered by the strand's probability, highest first."""
    kept = [s for s in scope.strands
            if probs[s.id] >= s.threshold
            and all(probs[f"{s.id}/{e.id}"] < scope.exclude_threshold for e in s.exclude)]
    return [s.id for s in sorted(kept, key=lambda s: -probs[s.id])]


def split_sentences(abstract: str) -> list[str]:
    text = re.sub(r"^\s*abstract[\s.:]*", "", abstract or "", flags=re.I).strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text)
    return [p.strip() for p in parts if len(p.split()) >= 6][:MAX_SENTENCES]


def evidence_questions(n: int, strand: Strand) -> dict:
    what = strand.yes or strand.question
    return {f"s{i}": _noul(f"Does `sentences[{i}]` on its own show that the paper fits this: {what}", "", "")
            for i in range(n)}


def pick_evidence(probs: dict[str, float], sentences: list[str]) -> str:
    """The sentence with the highest probability, copied exactly; the earliest wins a tie."""
    best = max(range(len(sentences)), key=lambda i: (probs[f"s{i}"], -i))
    return sentences[best]


@dataclass
class Judgement:
    probs: dict[str, float]
    kept: list[str]
    model: str
    evidence: str = ""
    evidence_probs: dict[str, float] = field(default_factory=dict)


def judge(jev: Jev, paper: Paper, scope: Scope) -> Judgement:
    probs, model = jev.ask(paper_state(paper), relevance_questions(scope))
    j = Judgement(probs, decide(probs, scope), model)
    sentences = split_sentences(paper.abstract)
    if j.kept and sentences:
        state = {"title": paper.title, "sentences": sentences}
        j.evidence_probs, _ = jev.ask(state, evidence_questions(len(sentences), scope.strand(j.kept[0])))
        j.evidence = pick_evidence(j.evidence_probs, sentences)
    return j
