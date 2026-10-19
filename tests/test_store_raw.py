"""store_raw.run must survive one failing source but not a run where all fail.

Fake sources stand in for the real ones, and RAW_DIR points at tmp_path, so no
test here touches the network or data/raw.
"""

import json

import pytest

from jobskills import config, store_raw


class _FakeSource:
    # Duck-typed rather than a Source subclass, so `critical` is set here too —
    # it does not come along from the ABC's default.
    def __init__(
        self,
        name: str,
        records: list[dict] | None = None,
        critical: bool = False,
    ):
        self.name = name
        self.records = records
        self.critical = critical

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
    path, n, failed = store_raw.run(srcs)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert n == 2
    assert [json.loads(line)["source"] for line in lines] == ["adzuna", "remotive"]
    assert [src.name for src in failed] == ["wwr"]
    assert "wwr failed" in capsys.readouterr().out


def test_every_source_failing_raises():
    with pytest.raises(RuntimeError):
        store_raw.run([_FakeSource("adzuna"), _FakeSource("wwr")])


def test_failed_critical_source_is_reported_not_raised():
    """Losing Adzuna keeps the partial data — the caller decides what it means.

    Raising here would discard the remote boards' postings, which are real. The
    run reports the failure instead, and run_weekly turns that into exit 3.
    """
    srcs = [
        _FakeSource("adzuna", critical=True),  # raises
        _FakeSource("remotive", [{"source": "remotive", "id": 2}]),
    ]
    path, n, failed = store_raw.run(srcs)

    assert n == 1
    assert json.loads(path.read_text(encoding="utf-8"))["source"] == "remotive"
    assert [src.name for src in failed] == ["adzuna"]
    assert [src.name for src in failed if src.critical] == ["adzuna"]


def test_failed_best_effort_source_is_not_critical():
    """A remote board dropping out is a thin week, not a degraded run."""
    srcs = [
        _FakeSource("adzuna", [{"source": "adzuna", "id": 1}], critical=True),
        _FakeSource("wwr"),  # raises
    ]
    _, n, failed = store_raw.run(srcs)

    assert n == 1
    assert [src.name for src in failed] == ["wwr"]
    assert [src.name for src in failed if src.critical] == []
