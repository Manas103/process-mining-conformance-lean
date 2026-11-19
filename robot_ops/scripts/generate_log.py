"""Regenerates data/session_log.csv and data/session_meta.csv. Run from
robot_ops/: .venv\\Scripts\\python.exe scripts\\generate_log.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ro import ro_generator  # noqa: E402

if __name__ == "__main__":
    log_df, case_meta_df = ro_generator.generate_log()
    (ROOT / "data").mkdir(exist_ok=True)
    log_df.to_csv(ROOT / "data" / "session_log.csv", index=False)
    case_meta_df.to_csv(ROOT / "data" / "session_meta.csv", index=False)
    print(f"wrote {len(log_df)} events across {case_meta_df['case_id'].nunique()} cases")
    print(case_meta_df["deviation_category"].value_counts().to_string())
