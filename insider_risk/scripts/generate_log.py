"""Regenerates data/case_log.csv and data/case_meta.csv. Run from
insider_risk/: .venv\\Scripts\\python.exe scripts\\generate_log.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ir import ir_generator  # noqa: E402

if __name__ == "__main__":
    log_df, case_meta_df = ir_generator.generate_case_log()
    (ROOT / "data").mkdir(exist_ok=True)
    log_df.to_csv(ROOT / "data" / "case_log.csv", index=False)
    case_meta_df.to_csv(ROOT / "data" / "case_meta.csv", index=False)
    print(f"wrote {len(log_df)} events across {case_meta_df['case_id'].nunique()} cases")
