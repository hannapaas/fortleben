from house.cli import main


def test_cli_runs_with_no_command():
    assert main([]) == 0
