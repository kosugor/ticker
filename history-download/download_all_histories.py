#!/usr/bin/env python3
"""Run every investment-history downloader."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DOWNLOADS = (
    ("Intesa Invest", "download_intesainvest_history.py", "intesainvest_history.csv"),
    (
        "Raiffeisen Invest",
        "download_raiffeiseninvest_history.py",
        "raiffeiseninvest_history.csv",
    ),
    ("NLB Fondovi", "download_nlbfondovi_history.py", "nlbfondovi_history.csv"),
    ("UniCredit Invest", "download_unicreditinvest_history.py", "unicreditinvest_history.csv"),
    ("WVP Fondovi", "download_wvpfondovi_history.py", "wvpfondovi_history.csv"),
    ("Vista Rica", "download_vistarica_history.py", "vistarica_history.csv"),
    ("Eclectica Capital", "download_eclecticacapital_history.py", "eclecticacapital_history.csv"),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download all configured provider histories."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="directory for both CSV files (default: current directory)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds passed to both downloaders (default: 30)",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    return args


def run_downloads(output_dir: Path, timeout: float) -> list[Path]:
    script_dir = Path(__file__).resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    for site_name, script_name, output_name in DOWNLOADS:
        output = output_dir / output_name
        command = (
            sys.executable,
            str(script_dir / script_name),
            "--output",
            str(output),
            "--timeout",
            str(timeout),
        )
        print(f"Downloading {site_name} history...", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"{script_name} failed with exit status {result.returncode}"
            )
        outputs.append(output.resolve())
        print(f"Finished: {output.resolve()}", flush=True)

    return outputs


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        outputs = run_downloads(args.output_dir, args.timeout)
    except (OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print("Downloaded histories:")
    for output in outputs:
        print(f"  {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
