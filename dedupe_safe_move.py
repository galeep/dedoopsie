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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src", type=Path, help="Source directory")
    parser.add_argument("--move-dir", type=Path, help="Where to move duplicates")
    parser.add_argument("--wet", action="store_true", help="Actually move files")
    parser.add_argument("--yes-really", action="store_true", help="Override safety prompt")
    parser.add_argument("--log", type=Path, help="Path to log file")
    parser.add_argument("--keeper", choices=["first", "oldest", "newest", "longest"], default="first", help="Strategy for keeper selection")
    parser.add_argument("--strict", action="store_true", help="Verify hash match after move")
    parser.add_argument("--verbose", action="store_true", help="Print per-file progress while hashing")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = args.log or Path(f"dupes-{timestamp}.csv") if not args.wet else (args.move_dir / f"dupes-{timestamp}.csv")

    if not args.move_dir:
        default_dir = Path(f".dedupe_quarantine/{timestamp}")
        args.move_dir = default_dir
        print(f"[INFO] Using default move-dir: {args.move_dir}")
    if args.wet:
        if not args.yes_really or os.environ.get("DUDE_ARE_YOU_SURE") != "YES":
            print("[ABORT] Wet mode requires --yes-really and DUDE_ARE_YOU_SURE=YES")
            return
    if args.wet:
        args.move_dir.mkdir(parents=True, exist_ok=True)

    print("[CONFIG]")
    print(f"- Mode: {'WET' if args.wet else 'DRYRUN'}")
    print(f"- Keeper strategy: {args.keeper}")
    print(f"- Move directory: {args.move_dir if args.move_dir else 'N/A (dryrun)'}")
    print(f"- Strict hash verification: {'ON' if args.strict else 'OFF'}")
    print(f"- Log file: {log_path}")

    all_files = scan_directory(args.src)
    dups = find_duplicates(all_files, verbose=args.verbose)
    print(f"[INFO] Found {len(dups)} duplicate groups.")

    total_wasted = 0
    with open(log_path, "w", newline="") as logfile:
        writer = csv.writer(logfile)
        writer.writerow(["GROUP_ID", "ACTION", "ORIGINAL_PATH", "DEST_PATH", "KEEPER_PATH", "GROUP_SIZE", "RECLAIMABLE", "HASH", "ERROR"])

        for i, group in enumerate(dups, 1):
            keeper = select_keeper(group, args.keeper)
            group_size = keeper.stat().st_size
            group_total = sum(f.stat().st_size for f in group)
            reclaimable = group_total - group_size
            print(f"[GROUP {i}] {len(group)} files, size each: {human_readable_size(group_size)}")
            print(f"  - Before: {human_readable_size(group_total)} | After: {human_readable_size(group_size)} | Reclaimable: {human_readable_size(reclaimable)}")

            keeper_hash = hash_file(keeper)
            writer.writerow([i, "KEEPER", str(keeper), "", str(keeper), group_total, reclaimable, keeper_hash, ""])

            for dupe in group:
                if dupe == keeper:
                    continue
                total_wasted += dupe.stat().st_size
                if args.wet:
                    result = safe_move(dupe, args.move_dir, verify_hash=args.strict)
                    if result[2]:
                        dupe_hash = hash_file(dupe)
                        writer.writerow([i, "MOVED", str(dupe), str(result[1]), str(keeper), group_total, reclaimable, dupe_hash, ""])
                    else:
                        dupe_hash = hash_file(dupe)
                        writer.writerow([i, "ERROR", str(dupe), str(result[1]), str(keeper), group_total, reclaimable, dupe_hash, result[3]])
                else:
                    dest = generate_safe_path(args.move_dir or Path("/dryrun"), dupe.name)
                    dupe_hash = hash_file(dupe)
                    writer.writerow([i, "DRYRUN", str(dupe), str(dest), str(keeper), group_total, reclaimable, dupe_hash, ""])

    print(f"[DONE] {len(dups)} dupe groups processed. Total duplicate space: {human_readable_size(total_wasted)}. Log saved to {log_path}")

if __name__ == "__main__":
    main()

