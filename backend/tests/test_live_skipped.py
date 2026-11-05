from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_live_directory_is_skipped_without_live_flag() -> None:
    """Plain pytest must never reach the network, whatever the shell env says."""
    env = os.environ.copy()
    env["ROOTA_PARSER"] = "keyword"
    # Even with a key present, without --live the live suite must skip.
    env.setdefault("ANTHROPIC_API_KEY", "sk-should-not-be-used")

    proc = subprocess.run(
        [
            sys.executable,
            "-X",
            "dev",
            "-m",
            "pytest",
            "tests/live",
            "-q",
            "-rs",
            "--tb=no",
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert re.search(r"\b\d+ skipped\b", output), output
    assert not re.search(r"\b[1-9]\d* passed\b", output), output
    assert not re.search(r"\b[1-9]\d* failed\b", output), output
    assert "live test: run with --live" in output
