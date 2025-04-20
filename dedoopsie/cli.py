"""
dedoopsie.cli
CLI entrypoint for the dedoopsie deduplication tool.
Supports dry-run and wet mode, keeper strategy selection, logging, and hash verification.
"""

import argparse
import os
import csv
from pathlib import Path
from datetime import datetime
from .core import scan_directory, find_duplicates, select_keeper, hash_file, safe_move, generate_safe_path, human_readable_size


def main():
    """Parse CLI arguments and run the deduplication process."""
    parser = argparse.ArgumentParser(description="Deduplicate files safely.")
    parser.add_argument("src", type=Path, help="Source directory to scan for duplicates")
    parser.add_argument("--move-dir", type=Path, help="Directory to move duplicates into (required for --wet)")
    parser.add_argument("--wet", action="store_true", help="Enable destructive mode (moves files)")
    parser.add_argument("--yes-really", action="store_true", help="Bypass wet mode safety prompt")
    parser.add_argument("--log", type=Path, help="Path to log CSV file")
    parser.add_argument("--keeper", choices=["first", "oldest", "newest", "longest"], default="first", help="File selection strategy for group keeper")
    parser.add_argument("--strict", action="store_true", help="Verify hash match after move")
    parser.add_argument("--verbose", action="store_true", help="Print hash progress during scan")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if not args.move_dir:
        default_dir = Path(f".dedoopsie_quarantine/{timestamp}")
        args.move_dir = default_dir
        print(f"[INFO] Using default move-dir: {args.move_dir}")

    log_path = args.log if args.log else (
        Path(f"dupes-{timestamp}.csv") if not args.wet else args.move_dir / f"dupes-{timestamp}.csv"
    )

    if args.wet:
        if not args.yes_really or os.environ.get("DUDE_ARE_YOU_SURE") != "YES":
            print("[ABORT] Wet mode requires --yes-really and DUDE_ARE_YOU_SURE=YES")
            return
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
        writer.writerow([
            "GROUP_ID", "ACTION", "ORIGINAL_PATH", "DEST_PATH",
            "KEEPER_PATH", "GROUP_SIZE", "RECLAIMABLE", "HASH", "ERROR"
        ])

        for i, group in enumerate(dups, 1):
            keeper = select_keeper(group, args.keeper)
            group_size = keeper.stat().st_size
            group_total = sum(f.stat().st_size for f in group)
            reclaimable = group_total - group_size

            print(f"[GROUP {i}] {len(group)} files, size each: {human_readable_size(group_size)}")
            print(f"  - Before: {human_readable_size(group_total)} | After: {human_readable_size(group_size)} | Reclaimable: {human_readable_size(reclaimable)}")

            keeper_hash = hash_file(keeper)
            writer.writerow([
                i, "KEEPER", str(keeper), "", str(keeper),
                group_total, reclaimable, keeper_hash, ""
            ])

            for dupe in group:
                if dupe == keeper:
                    continue

                total_wasted += dupe.stat().st_size

                if args.wet:
                    result = safe_move(dupe, args.move_dir, verify_hash=args.strict)
                    moved_path = result[1]

                    try:
                        dupe_hash = hash_file(moved_path)
                    except Exception as e:
                        dupe_hash = ""
                        result = (dupe, moved_path, False, f"Hash error: {e}")

                    action = "MOVED" if result[2] else "ERROR"
                    error_msg = "" if result[2] else result[3]

                    writer.writerow([
                        i, action, str(dupe), str(moved_path), str(keeper),
                        group_total, reclaimable, dupe_hash, error_msg
                    ])
                else:
                    dryrun_dest = generate_safe_path(args.move_dir or Path("/dryrun"), dupe.name)
                    dupe_hash = hash_file(dupe)
                    writer.writerow([
                        i, "DRYRUN", str(dupe), str(dryrun_dest), str(keeper),
                        group_total, reclaimable, dupe_hash, ""
                    ])

    print(f"[DONE] {len(dups)} dupe groups processed. Total duplicate space: {human_readable_size(total_wasted)}. Log saved to {log_path}")


if __name__ == "__main__":
    main()
