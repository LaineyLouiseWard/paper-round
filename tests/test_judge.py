import pytest

from paperround.judge import (Jev, JevError, decide, evidence_questions, judge, pick_evidence, read_answers,
                              relevance_questions, split_sentences)
from paperround.papers import Paper


def probs(**kw):
    base = {"floods": 0.0, "floods/projection": 0.0, "drought": 0.0}
    base.update({k.replace("__", "/"): v for k, v in kw.items()})
    return base


def test_questions_cover_every_strand_and_exclusion(scope):
    assert set(relevance_questions(scope)) == {"floods", "floods/projection", "drought"}


def test_keep_when_strand_reaches_threshold(scope):
    assert decide(probs(floods=0.7), scope) == ["floods"]
    assert decide(probs(floods=0.69), scope) == []


def test_exclusion_blocks_only_its_own_strand(scope):
    assert decide(probs(floods=0.95, floods__projection=0.8), scope) == []
    assert decide(probs(floods=0.95, floods__projection=0.8, drought=0.9), scope) == ["drought"]
    assert decide(probs(floods=0.95, floods__projection=0.69), scope) == ["floods"]


def test_per_strand_threshold_and_order(scope):
    assert decide(probs(drought=0.6), scope) == ["drought"]
    assert decide(probs(floods=0.75, drought=0.9), scope) == ["drought", "floods"]


def test_read_answers_rejects_missing_or_out_of_range():
    qs = {"a": {}, "b": {}}
    assert read_answers({"answers": {"a": {"noul": 0.2}, "b": {"noul": 1}}}, qs) == {"a": 0.2, "b": 1.0}
    with pytest.raises(JevError):
        read_answers({"answers": {"a": {"noul": 0.2}}}, qs)
    with pytest.raises(JevError):
        read_answers({"answers": {"a": {"noul": 0.2}, "b": {"noul": 1.3}}}, qs)
    with pytest.raises(JevError):
        read_answers({"answers": {"a": {"noul": "0.2"}, "b": {"noul": 0.1}}}, qs)


def test_split_sentences_drops_heading_and_fragments():
    text = "Abstract. Droughts end in floods across Europe. Short bit. We test forecasts of 2018 events in Ireland."
    assert split_sentences(text) == ["Droughts end in floods across Europe.",
                                     "We test forecasts of 2018 events in Ireland."]


def test_evidence_is_copied_exactly_and_ties_go_to_the_first():
    sentences = ["First long enough sentence here.", "Second long enough sentence here."]
    assert pick_evidence({"s0": 0.4, "s1": 0.9}, sentences) == sentences[1]
    assert pick_evidence({"s0": 0.9, "s1": 0.9}, sentences) == sentences[0]


def test_evidence_questions_point_at_each_sentence(scope):
    qs = evidence_questions(3, scope.strand("floods"))
    assert list(qs) == ["s0", "s1", "s2"]
    assert "`sentences[2]`" in qs["s2"]["instructions"]


class FakeJev:
    """Answers relevance questions from a table and sentence questions by favouring one sentence."""

    def __init__(self, answers, best_sentence=0):
        self.answers, self.best, self.calls = answers, best_sentence, []

    def ask(self, state, questions):
        self.calls.append(questions)
        if "sentences" in state:
            return {q: (0.9 if q == f"s{self.best}" else 0.1) for q in questions}, "jev-test"
        return {q: self.answers.get(q, 0.0) for q in questions}, "jev-test"


ABSTRACT = ("We study river floods across Ireland. Our forecasts give useful warnings two weeks ahead of floods. "
            "Results are compared with gauges in many catchments.")


def test_judge_kept_paper_gets_a_verbatim_sentence(scope):
    paper = Paper("Floods", "https://doi.org/10.1/f", "J", abstract=ABSTRACT)
    j = judge(FakeJev({"floods": 0.9}, best_sentence=1), paper, scope)
    assert j.kept == ["floods"]
    assert j.evidence == "Our forecasts give useful warnings two weeks ahead of floods."
    assert j.evidence in paper.abstract


def test_judge_rejected_paper_costs_one_request(scope):
    jev = FakeJev({"floods": 0.2})
    j = judge(jev, Paper("E-bikes", "https://x", "J", abstract=ABSTRACT), scope)
    assert j.kept == [] and j.evidence == "" and len(jev.calls) == 1


def test_jev_retries_then_raises():
    class Resp:
        def __init__(self, code, body=None):
            self.status_code, self.ok, self._body, self.text = code, code < 400, body, ""

        def json(self):
            return self._body

    class Session:
        def __init__(self, replies):
            self.replies = list(replies)

        def post(self, *a, **k):
            return self.replies.pop(0)

    import paperround.judge as jm
    jm.time.sleep = lambda s: None
    ok = Resp(200, {"model": "jev-1", "answers": {"a": {"noul": 0.5}}})
    assert Jev("k", session=Session([Resp(429), Resp(503), ok])).ask({}, {"a": {}}) == ({"a": 0.5}, "jev-1")
    with pytest.raises(JevError):
        Jev("k", session=Session([Resp(401)])).ask({}, {"a": {}})
