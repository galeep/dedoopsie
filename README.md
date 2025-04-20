# Dedupe Safe Move

This is a sane, test-backed utility for identifying and moving duplicate files within a directory tree. It favors safety, transparency, and auditability over blind automation.

### Features

- Dry run mode that logs everything but moves nothing
- Safe file movement with hash verification and collision-safe naming
- Grouping by file size and hash (fast and reliable)
- Structured logs with group IDs, reclaimable size, keeper strategy, and hashes
- CLI flags to discourage accidental file destruction
- Can be imported as a module or run from the command line

---

## Usage

### Dry run (recommended first step)

```bash
python -m dedupe.cli /path/to/scan
```

### Wet mode (actual file moves)

```bash
DUDE_ARE_YOU_SURE=YES python -m dedupe.cli /path/to/scan \
  --wet --yes-really \
  --move-dir /some/target/path \
  --keeper longest
```

### Configuration options

- `--move-dir`: where dupes will go (flat layout, names made unique)
- `--keeper`: choose which file to keep (first, oldest, newest, longest)
- `--strict`: verify hash after move before unlinking
- `--log`: write structured CSV output
- `--verbose`: see hashing progress in real time

---

## Log Format

CSV with the following columns:

```
GROUP_ID,ACTION,ORIGINAL_PATH,DEST_PATH,KEEPER_PATH,GROUP_SIZE,RECLAIMABLE,HASH,ERROR
```

Use it to debug, review, or rollback if needed. You'll thank yourself later.

---

## Python Usage

```python
from dedupe.core import scan_directory, find_duplicates, safe_move, select_keeper

files = scan_directory("/some/dir")
dupe_groups = find_duplicates(files)

for group in dupe_groups:
    keeper = select_keeper(group, "oldest")
    for file in group:
        if file != keeper:
            safe_move(file, Path("/quarantine"))
```

---

## Philosophy

This tool assumes:

- You're operating on a real system, not a toy dataset
- You care more about not breaking things than shaving microseconds
- Logging, reversibility, and testability matter

If that sounds like your vibe, you're in the right place.

---

## Tests

Run the test suite:

```bash
pytest
```

Dry run, safe move, collision handling, and keeper strategies are all covered.

---

## License

MIT. Use it, tweak it, improve it. Just don’t write a YOLO deduper and blame us.

---


![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)

---

## Example Log Output

```
[GROUP 17] 3 files, size each: 5.32 MB
  - Before: 15.96 MB | After: 5.32 MB | Reclaimable: 10.64 MB
```

---

## Install and Run

From the repo root:

```bash
pip install .
dedupe --help
```

Or without installing:

```bash
python -m dedupe.cli /your/target/path
```
