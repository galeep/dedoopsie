import os
import tempfile
from pathlib import Path
import subprocess
import csv
import pytest

"""
Tests for dryrun and wet modes of the dedoopsie CLI.
Uses real file operations in isolated temp directories.
Structured logs are parsed to validate behavior.
"""

def create_test_files(base_dir):
    """
    Create a test dataset including:
    - One unique file
    - Three files with identical content (dupes)
    - One zero-byte file
    """
    base = Path(base_dir)
    (base / "unique").write_text("I am unique")
    (base / "dupe1.txt").write_text("same content")
    (base / "dupe2.txt").write_text("same content")
    (base / "dupe3.txt").write_text("same content")
    (base / "zero.txt").write_text("")

def run_dedupe_cli(src_dir, move_dir, wet=False):
    """
    Run dedoopsie CLI via subprocess with appropriate flags.
    Uses DUDE_ARE_YOU_SURE=YES to unlock wet mode.
    """
    env = os.environ.copy()
    env["DUDE_ARE_YOU_SURE"] = "YES"

    args = [
        "/opt/local/bin/python",
        "-m", "dedoopsie.cli",
        str(src_dir),
        "--move-dir", str(move_dir),
        "--log", str(move_dir / "log.csv")
    ]

    if wet:
        args += ["--wet", "--yes-really"]

    subprocess.run(args, check=True, env=env)

def read_log(log_path):
    """Parse CSV log output from dedoopsie run."""
    with open(log_path) as f:
        reader = csv.DictReader(f)
        return list(reader)

@pytest.fixture
def temp_dirs():
    """
    Create isolated temp source and destination directories.
    Automatically cleaned up after test.
    """
    with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as dst_tmp:
        yield Path(src_tmp), Path(dst_tmp)

def test_deduper_dryrun(temp_dirs):
    """
    In dryrun mode:
    - Files should not be moved
    - Log should contain only DRYRUN actions
    """
    src_path, dst_path = temp_dirs
    create_test_files(src_path)
    run_dedupe_cli(src_path, dst_path, wet=False)
    log_entries = read_log(dst_path / "log.csv")
    assert all(row["ACTION"] == "DRYRUN" for row in log_entries)

def test_deduper_wet(temp_dirs):
    """
    In wet mode:
    - Two of the three dupes should be moved
    - Log should reflect MOVED actions
    - Moved files should exist in move-dir
    """
    src_path, dst_path = temp_dirs
    create_test_files(src_path)
    run_dedupe_cli(src_path, dst_path, wet=True)
    log_entries = read_log(dst_path / "log.csv")
    moved = [row for row in log_entries if row["ACTION"] == "MOVED"]
    assert len(moved) == 2  # dupe2 and dupe3 should have moved
    moved_names = [Path(row["DEST_PATH"]).name for row in moved]
    assert all((dst_path / name).exists() for name in moved_names)

