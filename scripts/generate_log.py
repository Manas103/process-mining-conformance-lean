"""Regenerates the 120,000-event synthetic log to data/event_log.csv and
data/case_meta.csv (both gitignored; regenerate with this script). CSV
rather than Parquet: no pyarrow/fastparquet is installed in this project's
venv, and every consumer in this repo loads through pandas/DuckDB anyway.

Usage: .venv\\Scripts\\python.exe scripts\\generate_log.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pm.generator import generate_log  # noqa: E402


def main() -> None:
    log_df, case_meta_df = generate_log()
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    log_df.to_csv(data_dir / "event_log.csv", index=False)
    case_meta_df.to_csv(data_dir / "case_meta.csv", index=False)
    print(f"wrote {len(log_df)} events across {len(case_meta_df)} cases to {data_dir}")
    print(case_meta_df["deviation_category"].value_counts().to_string())


if __name__ == "__main__":
    main()
