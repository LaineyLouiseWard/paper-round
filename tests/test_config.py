import pytest

from paperround.config import ConfigError, load_scope, load_settings


def test_scope_reads_strands_and_per_strand_threshold(scope):
    assert [s.id for s in scope.strands] == ["floods", "drought"]
    assert scope.strand("floods").threshold == 0.7
    assert scope.strand("drought").threshold == 0.6
    assert [e.id for e in scope.strand("floods").exclude] == ["projection"]


def test_label_falls_back_to_id_for_removed_strand(scope):
    assert scope.label("floods") == "Flood forecasting"
    assert scope.label("gone") == "gone"


@pytest.mark.parametrize("text, message", [
    ("strands: []", "at least one strand"),
    ("strands:\n  - {id: a, label: A}", "question"),
    ("strands:\n  - {id: a, label: A, question: q}\n  - {id: a, label: B, question: q}", "used twice"),
    ("threshold: 1.5\nstrands:\n  - {id: a, label: A, question: q}", "between 0 and 1"),
    ("strands:\n  - {id: a, label: A, question: q, exclude: [{id: x}]}", "needs an id and a question"),
])
def test_scope_rejects_bad_files(tmp_path, text, message):
    (tmp_path / "scope.yaml").write_text(text)
    with pytest.raises(ConfigError, match=message):
        load_scope(tmp_path / "scope.yaml")


def test_settings(cfg):
    assert cfg.feeds[0].name == "Journal A" and cfg.feeds[0].crossref_issn is None
    assert cfg.zotero_library_id == "123" and cfg.zotero_collection == "ABCDEFGH"
    assert cfg.send_when_empty is True and cfg.model == "jev-latest"


def test_settings_need_contact_email(tmp_path):
    (tmp_path / "config.yaml").write_text("feeds: []")
    with pytest.raises(ConfigError, match="contact_email"):
        load_settings(tmp_path / "config.yaml")


def test_missing_file_says_run_init(tmp_path):
    with pytest.raises(ConfigError, match="paperround init"):
        load_scope(tmp_path / "scope.yaml")


def test_starter_files_load():
    from paperround.cli import STARTER
    assert load_scope(STARTER / "scope.yaml").strands
    assert load_settings(STARTER / "config.yaml").feeds
