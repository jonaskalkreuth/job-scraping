"""run_weekly.main must finish the pipeline, then refuse to claim a bad week.

Every stage is monkeypatched: this test is about the exit code and the ordering,
not about fetching, cleaning or extracting, each of which is tested elsewhere.
"""

from pathlib import Path

import pytest

from jobskills import clean, extract, run_weekly, store_raw


class _FakeSource:
    def __init__(self, name: str, critical: bool = False):
        self.name = name
        self.critical = critical


@pytest.fixture
def stages(monkeypatch):
    """Stub clean and extract, recording that they ran."""
    ran: list[str] = []

    def fake_clean():
        ran.append("clean")
        return (10, 2, 8)

    def fake_extract():
        ran.append("extract")
        return (5, 1)

    monkeypatch.setattr(clean, "load", fake_clean)
    monkeypatch.setattr(extract, "load", fake_extract)
    return ran


def _patch_fetch(monkeypatch, failed: list[_FakeSource]):
    monkeypatch.setattr(
        store_raw, "run", lambda: (Path("jobs_test.jsonl"), 62, failed)
    )


def test_healthy_run_exits_zero(stages, monkeypatch):
    _patch_fetch(monkeypatch, [])

    run_weekly.main()  # no SystemExit

    assert stages == ["clean", "extract"]


def test_critical_failure_exits_degraded(stages, monkeypatch, capsys):
    _patch_fetch(monkeypatch, [_FakeSource("adzuna", critical=True)])

    with pytest.raises(SystemExit) as exc:
        run_weekly.main()

    assert exc.value.code == run_weekly.EXIT_DEGRADED
    # The pipeline must complete before the flag: the partial data is still
    # loaded and backed up, and only the week stamp is withheld.
    assert stages == ["clean", "extract"]
    out = capsys.readouterr().out
    assert "DEGRADED: adzuna failed" in out
    assert "=== done in" in out


def test_best_effort_failure_still_exits_zero(stages, monkeypatch, capsys):
    _patch_fetch(monkeypatch, [_FakeSource("wwr")])

    run_weekly.main()  # no SystemExit

    assert "DEGRADED" not in capsys.readouterr().out
