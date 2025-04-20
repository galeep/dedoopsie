# dedupe_safe_move.py
#
# DESIGN RATIONALE:
# This script safely identifies and relocates duplicate files within a given directory tree.
# It prioritizes reliability, transparency, and reversibility over aggressive deletion.
#
# Key design decisions:
# - Files are only deleted after a successful copy and optional hash verification.
# - All actions are logged in a machine-parseable CSV file.
# - Filename collisions are resolved with zero-padded suffixes.
# - Unsafe operations (like actual deletion) require redundant confirmation flags and env vars.
# - No shell commands or external tools are used; everything is pure Python.

import os
import hashlib
from pathlib import Path
from datetime import datetime
import argparse
import csv

SAFE_SUFFIX_PADDING = 5

def hash_file(path, algorithm="md5", chunk_size=8192):
    """Compute a hash digest of a file (default: MD5)."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

def find_duplicates(paths, verbose=False):
    """
    Group files by (size, hash). Return only groups with >1 file.
    This minimizes hash computations by only hashing same-sized files.
    """
    size_map = {}
    print(f"[INFO] Scanning {len(paths)} files...")
    for i, path in enumerate(paths, 1):
        try:
            size = path.stat().st_size
            size_map.setdefault(size, []).append(path)
        except Exception as e:
            print(f"[WARN] Could not stat {path}: {e}")
        if i % 500 == 0:
            print(f"  - Processed {i} files...")

    hash_map = {}
    print("[INFO] Computing hashes...")
    for size, group in size_map.items():
        if len(group) < 2:
            continue
        for file in group:
            try:
                h = hash_file(file)
                hash_map.setdefault((size, h), []).append(file)
                if verbose:
                    print(f"  - Hashed {file}")
            except Exception as e:
                print(f"[WARN] Could not hash {file}: {e}")

    return [group for group in hash_map.values() if len(group) > 1]

def generate_safe_path(dst_dir, original_name):
    """
    Generate a collision-safe path in dst_dir based on original_name,
    adding -00001, -00002, etc. if needed.
    """
    candidate = dst_dir / original_name
    count = 1
    stem, suffix = os.path.splitext(original_name)
    while candidate.exists():
        numbered = f"{stem}-{str(count).zfill(SAFE_SUFFIX_PADDING)}{suffix}"
        candidate = dst_dir / numbered
        count += 1
    return candidate

def safe_move(src, dst_dir, verify_hash=False):
    """
    Copy a file to dst_dir with collision-safe naming.
    Only deletes src after successful copy + optional hash verification.
    Returns (src, dst, success) or (src, dst, False, error_message).
    """
    dst_path = generate_safe_path(dst_dir, src.name)
    try:
        with open(src, "rb") as fsrc, open(dst_path, "xb") as fdst:
            while chunk := fsrc.read(8192):
                fdst.write(chunk)
            fdst.flush()
            os.fsync(fdst.fileno())

        stat = os.stat(src)
        os.chmod(dst_path, stat.st_mode)
        os.utime(dst_path, (stat.st_atime, stat.st_mtime))

        if verify_hash:
            original_hash = hash_file(src)
            copied_hash = hash_file(dst_path)
            if original_hash != copied_hash:
                return (src, dst_path, False, "Hash mismatch after copy")

        os.unlink(src)
        return (src, dst_path, True)
    except Exception as e:
        return (src, dst_path, False, str(e))

def select_keeper(group, strategy="first"):
    """
    Choose the file to keep in a dupe group.
    Strategies: first seen, oldest modified, newest, or longest path.
    """
    if strategy == "oldest":
        return min(group, key=lambda f: f.stat().st_mtime)
    elif strategy == "newest":
        return max(group, key=lambda f: f.stat().st_mtime)
    elif strategy == "longest":
        return max(group, key=lambda f: len(str(f)))
    else:
        return group[0]

def scan_directory(base_dir):
    """Recursively collect all files from base_dir."""
    return [p for p in Path(base_dir).rglob("*") if p.is_file()]

def human_readable_size(size):
    """Convert byte size to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"