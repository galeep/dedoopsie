import argparse
import os
import csv
from pathlib import Path
from datetime import datetime
from .core import *

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
