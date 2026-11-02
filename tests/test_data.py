"""Everything a run makes goes to one data folder, KEIKAKU_DATA_DIR (the volume, on Railway)."""

from house import client, db


def test_the_data_folder_comes_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("KEIKAKU_DATA_DIR", str(tmp_path / "volume"))
    assert db.data_dir() == tmp_path / "volume"
    db.connect().close()
    assert (tmp_path / "volume" / "keikaku.db").exists()
    assert client.cache_dir() == tmp_path / "volume" / "cache" / "responses"
    c = client.FakeClient(db.connect(":memory:"))
    c.store("k", {"data": 1})
    assert (tmp_path / "volume" / "cache" / "responses" / "k.json").exists()
    assert c.lookup("k") == {"data": 1}


def test_without_it_the_data_folder_is_the_repos_var(monkeypatch):
    monkeypatch.delenv("KEIKAKU_DATA_DIR", raising=False)
    monkeypatch.setattr(db, "dotenv_values", lambda path: {})
    assert db.data_dir() == db.ROOT / "var"
