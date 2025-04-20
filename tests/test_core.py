import os
import tempfile
import csv
from pathlib import Path
import dedoopsie.core as core

def create_test_files(base_dir):
    base = Path(base_dir)
    (base / "unique.txt").write_text("I am unique")
    (base / "dupe1.txt").write_text("same content")
    (base / "dupe2.txt").write_text("same content")
    (base / "dupe3.txt").write_text("same content")
    (base / "zero.txt").write_text("")

def test_find_duplicates_and_safe_move():
    with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as dst_tmp:
        src_path = Path(src_tmp)
        dst_path = Path(dst_tmp)
        create_test_files(src_path)
        all_files = core.scan_directory(src_path)
        dups = core.find_duplicates(all_files)
        assert len(dups) == 1
        group = dups[0]
        keeper = core.select_keeper(group, "first")
        for file in group:
            if file != keeper:
                result = core.safe_move(file, dst_path)
                assert result[2]
                assert (dst_path / result[1].name).exists()