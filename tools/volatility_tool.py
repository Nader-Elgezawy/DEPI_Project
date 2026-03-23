"""
Volatility 3 memory analysis module.
Runs common Volatility plugins against memory dump files.
"""

from __future__ import annotations

from typing import Callable

from tools.base import BaseTool, StepResult


class VolatilityTool(BaseTool):
    tool_id = "volatility"
    name = "Volatility 3 Memory Analysis"
    description = (
        "Analyze memory dumps with Volatility 3 framework. "
        "Runs common plugins such as pslist, pstree, netscan, and cmdline."
    )
    accepted_extensions = [".raw", ".dmp", ".mem", ".vmem", ".img", ".bin"]
    system_prerequisites = ["vol", "python3"]

    # Plugins to run (admin can extend)
    DEFAULT_PLUGINS = [
        "windows.info",
        "windows.pslist",
        "windows.pstree",
        "windows.netscan",
        "windows.cmdline",
    ]

    def run(
        self,
        filepath: str,
        emit: Callable[[str], None] | None = None,
    ) -> list[StepResult]:
        results: list[StepResult] = []
        plugins = self.DEFAULT_PLUGINS
        total = len(plugins) + 1  # +1 for the info step

        # Step 1 — verify Volatility installation
        if emit:
            emit(f"[Step 1/{total}] Verifying Volatility 3 installation ...")
        step = self._exec("vol --help | head -5", emit)
        results.append(step)
        if not step.success:
            if emit:
                emit(
                    "ERROR: Volatility 3 ('vol') is not installed or not on PATH.\n"
                    "Install with: pip install volatility3"
                )
            return results

        # Steps 2..N — run each plugin
        for idx, plugin in enumerate(plugins, start=2):
            if emit:
                emit(f"[Step {idx}/{total}] Running plugin: {plugin} ...")
            cmd = f"vol -f '{filepath}' {plugin}"
            step = self._exec(cmd, emit)
            results.append(step)
            if not step.success and emit:
                emit(f"  Plugin {plugin} returned non‑zero — this may be "
                     "expected if the dump is not a Windows image.")

        if emit:
            emit("Volatility analysis complete.")
        return results
