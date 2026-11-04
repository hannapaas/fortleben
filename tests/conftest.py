import pytest


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Every test keeps its database, cache, audits and releases in its own folder, never in the repo's var/."""
    monkeypatch.setenv("KEIKAKU_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"
