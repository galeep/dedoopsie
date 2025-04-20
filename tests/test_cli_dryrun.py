"""
Tests dryrun mode of the dedoopsie CLI using subprocess.
Validates structured CSV logging and file path presence.
"""

import os
import tempfile
import subprocess
import csv
from pathlib import Path

def create_dupes(base_dir):
    base = Path(base_dir)
    (base / "a.txt").write_text("dupe")
    (base / "b.txt").write_text("dupe")
    (base / "c.txt").write_text("dupe")

def test_dryrun_cli_logging():
    with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as log_tmp:
        src_path = Path(src_tmp)
        log_path = Path(log_tmp) / "log.csv"
        create_dupes(src_path)

        result = subprocess.run([
            "python", "-m", "dedoopsie.cli",
            str(src_path),
            "--log", str(log_path)
        ], capture_output=True, text=True)

        assert result.returncode == 0
        assert log_path.exists()

        with open(log_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert any(row["ACTION"] == "DRYRUN" for row in rows)
            assert all(row["DEST_PATH"] for row in rows if row["ACTION"] == "DRYRUN")

