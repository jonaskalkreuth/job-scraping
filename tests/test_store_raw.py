"""store_raw.run must survive one failing source but not a run where all fail.

Fake sources stand in for the real ones, and RAW_DIR points at tmp_path, so no
test here touches the network or data/raw.
"""

import json

import pytest

from jobskills import config, store_raw


class _FakeSource:
    def __init__(self, name: str, records: list[dict] | None = None):
        self.name = name
        self.records = records

    def fetch(self) -> list[dict]:
        if self.records is None:
            raise RuntimeError("403 Forbidden")
        return self.records


@pytest.fixture(autouse=True)
def raw_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")


def test_one_failing_source_still_writes_the_others(capsys):
    srcs = [
        _FakeSource("adzuna", [{"source": "adzuna", "id": 1}]),
        _FakeSource("wwr"),  # raises
        _FakeSource("remotive", [{"source": "remotive", "id": 2}]),
    ]
    path, n = store_raw.run(srcs)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert n == 2
    assert [json.loads(line)["source"] for line in lines] == ["adzuna", "remotive"]
    assert "wwr failed" in capsys.readouterr().out


def test_every_source_failing_raises():
    with pytest.raises(RuntimeError):
        store_raw.run([_FakeSource("adzuna"), _FakeSource("wwr")])
