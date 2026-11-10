#!/usr/bin/env python3
"""Resumable, append-only Collatz frontier scans without SQLite."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

FRONTIER = 2075 * (1 << 60)
FIELDS = ("range", "completed", "unresolved", "longest_steps", "highest_peak")

def verify_record(n, max_steps):
    peak = n
    steps = 0
    while n != 1 and steps < max_steps:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        peak = max(peak, n)
        steps += 1
    return steps, peak, n == 1

def load(path, start, count, chunk, max_steps):
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as e:
                raise ValueError(f"Invalid checkpoint line {line_no}: {e}") from e
            expected = start + len(records) * chunk
            length = min(chunk, count - len(records) * chunk)
            if length <= 0 or row.get("start") != str(expected) or row.get("end") != str(expected + length - 1) or row.get("max_steps") != max_steps or row.get("completed", 0) + row.get("unresolved", 0) != length:
                raise ValueError(f"Checkpoint mismatch at line {line_no}; refusing unsafe resume")
            records.append(row)
    return records

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", type=int, default=FRONTIER + 1)
    p.add_argument("--count", type=int, default=1_000_000)
    p.add_argument("--chunk", type=int, default=100_000)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=100_000)
    p.add_argument("--checkpoint", type=Path, default=Path("frontier-checkpoint.jsonl"))
    p.add_argument("--binary", type=Path, default=Path("target/release/syracuse-rs"))
    p.add_argument("--verify", action="store_true", help="Recalculate chunk record trajectories in independent Python")
    args = p.parse_args()
    if min(args.start, args.count, args.chunk, args.workers, args.max_steps) < 1:
        p.error("all numeric arguments must be positive")
    if args.checkpoint.is_symlink():
        p.error("checkpoint must not be a symlink")
    rows = load(args.checkpoint, args.start, args.count, args.chunk, args.max_steps)
    print(f"resume={len(rows)} checkpoint={args.checkpoint}", flush=True)
    with args.checkpoint.open("a", encoding="utf-8") as output:
        for index in range(len(rows), (args.count - 1) // args.chunk + 1):
            lo = args.start + index * args.chunk
            hi = min(args.start + args.count - 1, lo + args.chunk - 1)
            command = [str(args.binary.resolve()), "--start", str(lo), "--end", str(hi), "--workers", str(args.workers), "--max-steps", str(args.max_steps)]
            t = time.monotonic()
            run = subprocess.run(command, text=True, capture_output=True, check=True)
            values = dict(re.findall(r"([a-z_]+)=([^\s]+)", run.stdout))
            if values.get("range") != f"{lo}..={hi}":
                raise RuntimeError(f"Unexpected scan range: {run.stdout}")
            completed, unresolved = int(values["completed"]), int(values["unresolved"])
            if completed + unresolved != hi - lo + 1:
                raise RuntimeError("Incomplete chunk; not checkpointing")
            row = dict(start=str(lo), end=str(hi), max_steps=args.max_steps,
                       completed=completed, unresolved=unresolved,
                       elapsed_seconds=round(time.monotonic()-t, 6),
                       longest_steps=int(values["longest_steps"]) if "longest_steps" in values else None,
                       longest_start=values.get("start"), highest_peak=values.get("highest_peak"),
                       verified_records=False)
            # Both records share a 'start' label in CLI output; parse lines separately.
            for line in run.stdout.splitlines():
                if line.startswith("longest_steps="):
                    row["longest_start"] = line.split("start=", 1)[1].strip()
                elif line.startswith("highest_peak="):
                    row["highest_peak"] = line.split()[0].split("=",1)[1]
                    row["highest_start"] = line.split("start=",1)[1].strip()
            if args.verify:
                if row["longest_steps"] is not None:
                    steps, _, reached = verify_record(int(row["longest_start"]), args.max_steps)
                    if not reached or steps != row["longest_steps"]:
                        raise RuntimeError("Independent longest-record verification failed")
                if row["highest_peak"] is not None:
                    _, peak, reached = verify_record(int(row["highest_start"]), args.max_steps)
                    if not reached or peak != int(row["highest_peak"]):
                        raise RuntimeError("Independent highest-peak verification failed")
                row["verified_records"] = True
            output.write(json.dumps(row, sort_keys=True) + "\n")
            output.flush()
            os.fsync(output.fileno())
            rows.append(row)
            print(f"chunk={index+1} range={lo}..={hi} completed={completed} unresolved={unresolved} verified_records={row['verified_records']}", flush=True)
    total = sum(r["completed"] for r in rows)
    unresolved = sum(r["unresolved"] for r in rows)
    longest = max((r for r in rows if r["longest_steps"] is not None), key=lambda r:r["longest_steps"], default=None)
    highest = max((r for r in rows if r["highest_peak"] is not None), key=lambda r:int(r["highest_peak"]), default=None)
    print(f"total_completed={total} total_unresolved={unresolved}")
    if longest: print(f"longest_steps={longest['longest_steps']} start={longest['longest_start']}")
    if highest: print(f"highest_peak={highest['highest_peak']} start={highest['highest_start']}")
    print("Verification of record trajectories is not an independent exhaustive verification of the range.")

if __name__ == "__main__":
    main()