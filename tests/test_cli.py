from paperround.cli import main


def test_init_writes_starter_files_and_keeps_existing(tmp_path, capsys):
    (tmp_path / "scope.yaml").write_text("mine")
    assert main(["--dir", str(tmp_path), "init"]) == 0
    assert (tmp_path / "scope.yaml").read_text() == "mine"
    assert (tmp_path / "config.yaml").exists() and (tmp_path / ".gitignore").exists()
    assert (tmp_path / ".github" / "workflows" / "paper-round.yml").exists()
    assert "kept your scope.yaml" in capsys.readouterr().out


def test_bad_settings_exit_2(tmp_path, capsys):
    (tmp_path / "config.yaml").write_text("feeds: []")
    (tmp_path / "scope.yaml").write_text("strands: []")
    assert main(["--dir", str(tmp_path), "run", "--dry-run"]) == 2
    assert "Settings problem" in capsys.readouterr().err
