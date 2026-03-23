"""
Report generation utilities.
Saves analysis results to plain‑text files in the reports/ directory.
"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def save_report(
    report_dir: str,
    tool_id: str,
    filename: str,
    log_lines: list[str],
) -> str:
    """Persist *log_lines* as a timestamped text report.

    Returns the absolute path to the saved report file.
    """
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in (".", "-", "_") else "_" for c in filename)
    report_name = f"{tool_id}_{safe_name}_{timestamp}.txt"
    report_path = os.path.join(report_dir, report_name)

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("Forensics Dashboard — Analysis Report\n")
        fh.write(f"{'=' * 50}\n")
        fh.write(f"Tool   : {tool_id}\n")
        fh.write(f"File   : {filename}\n")
        fh.write(f"Date   : {timestamp}\n")
        fh.write(f"{'=' * 50}\n\n")
        for line in log_lines:
            fh.write(line + "\n")

    logger.info("Report saved: %s", report_path)
    return report_path
