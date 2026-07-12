from __future__ import annotations

import fcntl
import logging
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

from ticker.config import PROJECT_ROOT, Settings
from ticker.logging_config import configure_logging


LOGGER = logging.getLogger("run_collectors")
COLLECTORS = ("collect_exchange_rate.py", "collect_fund_value.py")


@contextmanager
def process_lock(path: Path) -> Iterator[TextIO | None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield None
            return
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(Path("/proc/self").resolve().name))
        lock_file.flush()
        yield lock_file
    finally:
        lock_file.close()


def run_collectors(project_root: Path = PROJECT_ROOT) -> dict[str, int]:
    results: dict[str, int] = {}
    for script_name in COLLECTORS:
        script_path = project_root / script_name
        try:
            completed = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=project_root,
                text=True,
                capture_output=True,
                check=False,
            )
            results[script_name] = completed.returncode
            log = LOGGER.info if completed.returncode == 0 else LOGGER.error
            log(
                "collector finished script=%s exit_code=%d stdout=%r stderr=%r",
                script_name,
                completed.returncode,
                completed.stdout.strip(),
                completed.stderr.strip(),
            )
        except Exception:
            results[script_name] = -1
            LOGGER.exception("could not launch collector script=%s", script_name)
    return results


def main() -> int:
    settings = Settings.from_env()
    configure_logging(settings.log_path)
    try:
        with process_lock(settings.lock_path) as lock:
            if lock is None:
                LOGGER.info("another orchestrator run is active; skipping")
                return 0
            results = run_collectors()
            failures = [name for name, code in results.items() if code != 0]
            if failures:
                LOGGER.error("orchestrator completed with collector failures scripts=%s", failures)
            else:
                LOGGER.info("orchestrator completed successfully")
    except Exception:
        LOGGER.exception("orchestrator failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

