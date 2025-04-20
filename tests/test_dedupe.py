import os
import tempfile
from pathlib import Path
import subprocess
import csv
import pytest

# DESIGN RATIONALE:
# These tests validate dryrun and wet modes of the dedoopsie CLI.
# They use real file operations in isolated temp directories.
# Logging is parsed to assert behavior without inspecting stdout.

def create_test_files(base_dir):
    base = Path(base_dir)
    (base / "unique").write_text("I am unique")
    (base / "dupe1.txt").write_text("same content")
    (base / "dupe2.txt").write_text("same content")
    (base / "dupe3.txt").write_text("same content")
    (base / "zero.txt").write_text("")


def run_dedupe(src_dir, move_dir, wet=False):
    env = os.environ.copy()
    env["DUDE_ARE_YOU_SURE"] = "YES"
    log_path = move_dir / "log.csv"
    args = [
        "/opt/local/bin/python",
        "-m", "dedoopsie.cli",
        str(src_dir),
        "--move-dir", str(move_dir),
        "--log", str(log_path)
    ]
    if wet:
        args += ["--wet", "--yes-really"]
    subprocess.run(args, check=True, env=env)

def read_log(log_path):
    with open(log_path) as f:
        reader = csv.DictReader(f)
        return list(reader)

@pytest.fixture
def temp_dirs():
    with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as dst_tmp:
        yield Path(src_tmp), Path(dst_tmp)

def test_deduper_dryrun(temp_dirs):
    src_path, dst_path = temp_dirs
    create_test_files(src_path)
    run_dedupe(src_path, dst_path, wet=False)
    log_entries = read_log(dst_path / "log.csv")
    assert any(row["ACTION"] == "KEEPER" for row in log_entries)
    assert all(row["ACTION"] in {"DRYRUN", "KEEPER"} for row in log_entries)

def test_deduper_wet(temp_dirs):
    src_path, dst_path = temp_dirs
    create_test_files(src_path)
    run_dedupe(src_path, dst_path, wet=True)
    log_entries = read_log(dst_path / "log.csv")
    moved = [row for row in log_entries if row["ACTION"] == "MOVED"]
    assert len(moved) == 2
    moved_names = [Path(row["DEST_PATH"]).name for row in moved]
    assert all((dst_path / name).exists() for name in moved_names)
