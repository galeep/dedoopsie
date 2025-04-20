import os
import tempfile
import csv
from pathlib import Path
import dedoopsie.core as core

def create_test_group_with_metadata(base_dir):
    base = Path(base_dir)
    oldest = base / "oldest.txt"
    newest = base / "newest.txt"
    longest = base / "this-is-a-very-long-filename.txt"
    [f.write_text("same content") for f in [oldest, newest, longest]]
    os.utime(oldest, (1_000_000_000, 1_000_000_000))
    os.utime(newest, None)
    os.utime(longest, (1_500_000_000, 1_500_000_000))

def test_keeper_strategies():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        create_test_group_with_metadata(path)
        all_files = core.scan_directory(path)
        groups = core.find_duplicates(all_files)
        group = groups[0]
        assert core.select_keeper(group, "oldest").name == "oldest.txt"
        assert core.select_keeper(group, "newest").name == "newest.txt"
        assert core.select_keeper(group, "longest").name.startswith("this-is-a-very-long")

def test_generate_safe_path_collision():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        basefile = path / "dupe.txt"
        basefile.write_text("x")
        for i in range(3):
            clone = path / f"dupe-{str(i+1).zfill(5)}.txt"
            clone.write_text("x")
        safe = core.generate_safe_path(path, "dupe.txt")
        assert safe.name.startswith("dupe-")
        assert safe.name.endswith(".txt")
        assert safe != basefile

def test_hash_mismatch_detection():
    with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as dst_tmp:
        src = Path(src_tmp) / "test.txt"
        src.write_text("original")
        dst = Path(dst_tmp)
        moved_path = dst / src.name
        moved_path.write_text("corrupted content")
        original_hash = core.hash_file(src)
        moved_hash = core.hash_file(moved_path)
        assert original_hash != moved_hash