from house.cli import main


def test_cli_runs_with_no_command():
    assert main([]) == 0


def test_a_run_that_wont_fit_its_cap_is_not_started(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "not-a-real-key")  # the live client refuses on the estimate, before any call
    from house import budget
    assert budget.estimate_run(3400, 1, {"desk_model": "wonder"}) > budget.estimate_run(3400, 1, {"desk_model": "spark"})
    assert budget.estimate_run(6800, 2, {}) > 2 * budget.estimate_run(3400, 1, {})  # the pass back
    assert 0.95 < budget.estimate_run(3397, None, {}) < 1.4  # 晩餐's run on the defaults cost $0.92 (4 Nov)
    assert main(["--db", str(tmp_path / "k.db"), "--cap", "0.05", "run", "bansan"]) == 1
    assert "Nothing was started" in capsys.readouterr().out


def test_an_unknown_work_and_a_missing_recording_say_so_plainly(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert main(["--db", str(tmp_path / "k.db"), "run", "no-such-work"]) == 1
    assert "unknown work" in capsys.readouterr().out
    assert main(["--db", str(tmp_path / "k.db"), "--replay", "--cap", "5", "run", "warogoku"]) == 1
    assert "no recorded run to replay" in capsys.readouterr().out
