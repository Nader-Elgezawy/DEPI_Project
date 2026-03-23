"""
Volatility Plugin Runner integration module.
Wraps the user's vol_runner.py script to run all Volatility plugins
against a memory dump and produce a JSON results file.

Setup:
  1. Place vol_runner.py in the project root (or set VOL_RUNNER_SCRIPT).
  2. Ensure 'vol' (Volatility 3) or 'vol.py' is on PATH.
"""

from __future__ import annotations

import os
import shutil
from typing import Callable

from tools.base import BaseTool, StepResult

# Path to vol_runner.py — admin can override via env var
_DEFAULT_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "vol_runner.py",
)
VOL_RUNNER_SCRIPT = os.environ.get("VOL_RUNNER_SCRIPT", _DEFAULT_SCRIPT)


def _find_vol_binary() -> str | None:
    """Find the Volatility binary on PATH (vol, vol3, vol.py)."""
    for name in ("vol", "vol3", "volatility3"):
        path = shutil.which(name)
        if path:
            return path
    return None


class VolRunnerTool(BaseTool):
    tool_id = "vol_runner"
    name = "Volatility Plugin Runner"
    description = (
        "Run all Volatility 2/3 plugins against a memory dump using "
        "vol_runner.py. Produces per-plugin text output and a unified "
        "results.json file with full forensic data."
    )
    accepted_extensions = [".raw", ".dmp", ".mem", ".vmem", ".img", ".bin"]
    system_prerequisites = ["python3"]

    @classmethod
    def check_prerequisites(cls) -> list[dict]:
        """Check for python3, a Volatility binary, and vol_runner.py."""
        results = super().check_prerequisites()

        # Check for vol binary
        vol_bin = _find_vol_binary()
        results.append({
            "program": "vol / vol3 / volatility3",
            "installed": vol_bin is not None,
        })

        # Check for vol_runner.py script
        results.append({
            "program": f"vol_runner.py ({VOL_RUNNER_SCRIPT})",
            "installed": os.path.isfile(VOL_RUNNER_SCRIPT),
        })

        return results

    def run(
        self,
        filepath: str,
        emit: Callable[[str], None] | None = None,
    ) -> list[StepResult]:
        results: list[StepResult] = []

        # Step 1 — verify vol_runner.py exists
        if emit:
            emit("[Step 1/4] Checking for vol_runner.py ...")
        if not os.path.isfile(VOL_RUNNER_SCRIPT):
            msg = (
                f"vol_runner.py not found at: {VOL_RUNNER_SCRIPT}\n"
                "Place vol_runner.py in the project root directory or set "
                "the VOL_RUNNER_SCRIPT environment variable."
            )
            if emit:
                emit(f"  ERROR: {msg}")
            results.append(StepResult(
                command="(check vol_runner.py)",
                output=msg,
                return_code=1,
                success=False,
            ))
            return results

        if emit:
            emit(f"  Found: {VOL_RUNNER_SCRIPT}")
        results.append(StepResult(
            command="(check vol_runner.py)",
            output=f"Found: {VOL_RUNNER_SCRIPT}",
            return_code=0,
            success=True,
        ))

        # Step 2 — find Volatility binary
        if emit:
            emit("[Step 2/4] Locating Volatility binary ...")
        vol_bin = _find_vol_binary()
        if not vol_bin:
            msg = (
                "No Volatility binary found on PATH. "
                "Install Volatility 3: pip install volatility3"
            )
            if emit:
                emit(f"  ERROR: {msg}")
            results.append(StepResult(
                command="(find volatility)",
                output=msg,
                return_code=1,
                success=False,
            ))
            return results

        if emit:
            emit(f"  Found: {vol_bin}")
        results.append(StepResult(
            command="(find volatility)",
            output=f"Found: {vol_bin}",
            return_code=0,
            success=True,
        ))

        # Step 3 — build output directory
        if emit:
            emit("[Step 3/4] Preparing output directory ...")
        basename = os.path.splitext(os.path.basename(filepath))[0]
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reports",
            f"{basename}_vol_runner",
        )
        os.makedirs(output_dir, exist_ok=True)
        if emit:
            emit(f"  Output directory: {output_dir}")
        results.append(StepResult(
            command="(prepare output dir)",
            output=f"Output directory: {output_dir}",
            return_code=0,
            success=True,
        ))

        # Step 4 — run vol_runner.py with --vol3
        if emit:
            emit("[Step 4/4] Running vol_runner.py (this may take a while) ...")
        cmd = (
            f"python3 '{VOL_RUNNER_SCRIPT}' "
            f"-f '{filepath}' "
            f"--vol3 '{vol_bin}' "
            f"-o '{output_dir}'"
        )
        step = self._exec(cmd, emit)
        results.append(step)

        # Show location of results.json if it was created
        results_json = os.path.join(output_dir, "results.json")
        if os.path.isfile(results_json):
            if emit:
                emit(f"Results JSON: {results_json}")
        else:
            if emit:
                emit("WARNING: results.json was not created. Check the output above for errors.")

        if emit:
            emit("vol_runner.py execution complete.")
        return results
