from pathlib import Path
from unittest.mock import patch

from run_collectors import COLLECTORS, process_lock, run_collectors


def test_lock_rejects_overlap(tmp_path) -> None:
    path = tmp_path / "ticker.lock"
    with process_lock(path) as first:
        assert first is not None
        with process_lock(path) as second:
            assert second is None


def test_both_collectors_run_even_after_failure(tmp_path) -> None:
    results = [type("Result", (), {"returncode": 1, "stdout": "", "stderr": "bad"})(),
               type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()]
    with patch("run_collectors.subprocess.run", side_effect=results) as subprocess_run:
        outcome = run_collectors(Path(tmp_path))
    assert subprocess_run.call_count == 2
    assert outcome == {COLLECTORS[0]: 1, COLLECTORS[1]: 0}

