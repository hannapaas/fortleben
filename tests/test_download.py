"""The editor's download: a zip with the run's full record and one readable file per edition.
Built from the recorded fixtures/bansan/run.json, loaded into a fresh database."""

import io
import json
import zipfile

import pytest

from house import fixture
from house.cli import main
from house.client import FIXTURES
from house.db import connect


@pytest.fixture
def recorded(tmp_path):
    """The recorded 晩餐 run, loaded row by row into a fresh database."""
    rec = json.loads((FIXTURES / "bansan" / "run.json").read_text(encoding="utf-8"))
    db = tmp_path / "k.db"
    conn = connect(db)
    conn.execute("PRAGMA foreign_keys = OFF")  # the record holds this run's rows, not every row they point to
    for table in ("work", "run", *fixture.TABLES):
        for row in [rec[table]] if isinstance(rec[table], dict) else rec[table]:
            row = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()}
            conn.execute(f"INSERT OR REPLACE INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                         list(row.values()))
    ed = conn.execute("INSERT INTO edition (work_id) VALUES ('bansan')").lastrowid
    conn.execute("INSERT INTO release (edition_id, run_id, version, body) VALUES (?,?,?,?)",
                 (ed, rec["run"]["id"], "v0.1", json.dumps(rec["release"], ensure_ascii=False)))
    conn.commit()
    return conn, rec, db


def test_download_holds_the_record_and_one_readable_file_per_edition(recorded):
    conn, rec, _ = recorded
    run_id = rec["run"]["id"]
    z = zipfile.ZipFile(io.BytesIO(fixture.download(conn, run_id)))
    folder = f"bansan-run{run_id}"
    assert sorted(z.namelist()) == [f"{folder}/bansan-{v}.md" for v in ("casual", "curious", "student")] + [f"{folder}/run.json"]
    assert json.loads(z.read(f"{folder}/run.json")) == rec  # the same record export writes
    release = rec["release"]
    for view, paras in release["views"].items():
        md = z.read(f"{folder}/bansan-{view}.md").decode("utf-8")
        assert md.startswith(f"# {release['title']}") and release["author"] in md
        assert "Aozora Bunko (青空文庫)" in md and "入力：" in md  # the attribution and the colophon, verbatim
        for p in paras:
            for sentence in filter(None, p["en"].split(". ")):
                assert sentence[:30] in md
            for n in p["notes"]:
                assert n["body"] in md
        assert md.count("[^") == 2 * sum(len(p["notes"]) for p in paras)  # a mark in the text and a footnote each


def test_the_cli_writes_the_zip(recorded, tmp_path, capsys):
    _, rec, db = recorded
    out = tmp_path / "copy.zip"
    assert main(["--db", str(db), "download", "bansan", "--out", str(out)]) == 0
    assert f"bansan-run{rec['run']['id']}/run.json" in zipfile.ZipFile(out).namelist()
    assert main(["--db", str(db), "download", "shuchu"]) == 1
    assert "Not downloaded" in capsys.readouterr().out
