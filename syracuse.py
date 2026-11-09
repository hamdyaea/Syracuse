#!/usr/bin/env python3
# Developer: Hamdy Abou El Anein
# Contact: info@daylightlinux.ch
# SPDX-License-Identifier: GPL-3.0-only
"""Collatz/Syracuse research CLI (Python standard library core)."""
from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import sqlite3
import time
from pathlib import Path


def syracuse(number: int, max_steps: int = 100_000) -> list[int]:
    """Return the exact sequence through 1, or raise if the limit is reached."""
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("Starting number must be a positive integer")
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    sequence = [number]
    for _ in range(max_steps):
        if number == 1:
            return sequence
        number = number // 2 if number % 2 == 0 else 3 * number + 1
        sequence.append(number)
    if number == 1:
        return sequence
    raise RuntimeError("Maximum steps reached before 1")


def analyze(number: int, max_steps: int = 100_000) -> tuple[int, int, int, str]:
    """Return (start, steps, peak, status). Limits are NOT counterexamples."""
    if number < 1 or max_steps < 1:
        raise ValueError("number and max_steps must be positive")
    current, peak = number, number
    seen = set()
    for steps in range(max_steps + 1):
        if current == 1:
            return number, steps, peak, "reached_1"
        if current in seen:
            return number, steps, peak, "cycle"
        if steps == max_steps:
            return number, steps, peak, "limit"
        seen.add(current)
        current = current // 2 if current % 2 == 0 else 3 * current + 1
        peak = max(peak, current)
    raise AssertionError("unreachable")


def _worker_batch(job: tuple[list[int], int]) -> list[tuple[int, int, int, str]]:
    """Compute a batch with a bounded per-process stopping-time cache.

    The cache stores only proven-to-reach-1 tails, never limited trajectories.
    Peaks and stopping times use the original, uncompressed Collatz steps.
    """
    numbers, max_steps = job
    cache: dict[int, tuple[int, int]] = {1: (0, 1)}
    output = []
    for start in numbers:
        n = start
        path: list[int] = []
        seen: set[int] = set()
        peak = n
        status = "limit"
        steps = 0
        while True:
            tail = cache.get(n)
            if tail is not None and steps + tail[0] <= max_steps:
                steps += tail[0]
                peak = max(peak, tail[1])
                status = "reached_1"
                break
            if n == 1:
                status = "reached_1"
                break
            if n in seen:
                status = "cycle"
                break
            if steps == max_steps:
                break
            seen.add(n)
            path.append(n)
            n = n // 2 if n % 2 == 0 else 3 * n + 1
            peak = max(peak, n)
            steps += 1
        output.append((start, steps, peak, status))
        if status == "reached_1":
            # Backfill the exact remaining time and maximum for each tail.
            remaining = steps - len(path)
            tail_peak = cache[n][1] if n in cache else n
            for value in reversed(path):
                remaining += 1
                tail_peak = max(value, tail_peak)
                cache[value] = (remaining, tail_peak)
            if len(cache) > 100_000:
                cache = {1: (0, 1)}
    return output


def init_db(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS results (
        start INTEGER PRIMARY KEY, steps INTEGER NOT NULL,
        peak TEXT NOT NULL, status TEXT NOT NULL,
        max_steps INTEGER NOT NULL)""")
    connection.execute("CREATE INDEX IF NOT EXISTS results_status ON results(status)")
    connection.commit()


def scan(start: int, end: int, max_steps: int, workers: int,
         database: Path, batch_size: int = 1000) -> None:
    """Scan in bounded batches with thread-local SQLite reader and parent writer."""
    if not 1 <= start <= end or max_steps < 1 or workers < 1 or batch_size < 1:
        raise ValueError("Invalid scan parameters")
    if end > 2**63 - 1:
        raise ValueError("SQLite INTEGER start keys must fit signed 64-bit")
    connection = sqlite3.connect(database)
    try:
        init_db(connection)
        started = time.monotonic()
        processed = 0
        best_steps = (-1, 0)
        best_peak = (-1, 0)

        def jobs():
            # Pool feeder may run this generator in another thread.
            reader = sqlite3.connect(database, timeout=30)
            try:
                for low in range(start, end + 1, batch_size):
                    high = min(end, low + batch_size - 1)
                    known = {
                        n: (status, limit)
                        for n, status, limit in reader.execute(
                            "SELECT start, status, max_steps FROM results "
                            "WHERE start BETWEEN ? AND ?", (low, high)
                        )
                    }
                    pending = [
                        n for n in range(low, high + 1)
                        if n not in known or
                        (known[n][0] == "limit" and known[n][1] < max_steps)
                    ]
                    if pending:
                        yield pending, max_steps
            finally:
                reader.close()

        def consume(batches):
            nonlocal processed, best_steps, best_peak
            for results in batches:
                rows = []
                for n, steps, peak, status in results:
                    rows.append((n, steps, str(peak), status, max_steps))
                    processed += 1
                    if status == "reached_1":
                        if steps > best_steps[0]:
                            best_steps = (steps, n)
                        if peak > best_peak[0]:
                            best_peak = (peak, n)
                connection.executemany(
                    "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?)", rows
                )
                connection.commit()
                if processed % (batch_size * 10) < len(results):
                    print(f"Processed {processed:,} new values in "
                          f"{time.monotonic()-started:.1f}s", flush=True)

        if workers == 1:
            consume(map(_worker_batch, jobs()))
        else:
            # The feeder owns a separate read connection; only parent writes.
            with mp.Pool(workers) as pool:
                consume(pool.imap(_worker_batch, jobs(), chunksize=1))

        total, unresolved = connection.execute(
            "SELECT COUNT(*), SUM(status != 'reached_1') FROM results "
            "WHERE start BETWEEN ? AND ?", (start, end)
        ).fetchone()
        print(f"Stored: {total:,} | Unresolved: {unresolved or 0:,} "
              f"| New: {processed:,} | Elapsed: {time.monotonic()-started:.2f}s")
        if best_steps[0] >= 0:
            print(f"Longest newly completed trajectory: {best_steps[0]} "
                  f"steps (start={best_steps[1]})")
            print(f"Largest newly completed peak: {best_peak[0]} "
                  f"(start={best_peak[1]})")
    finally:
        connection.close()


def export_csv(database: Path, destination: Path) -> None:
    with sqlite3.connect(database) as connection, destination.open(
        "w", newline="", encoding="utf-8"
    ) as output:
        writer = csv.writer(output)
        writer.writerow(("start", "steps", "peak", "status", "max_steps"))
        writer.writerows(connection.execute(
            "SELECT start, steps, peak, status, max_steps FROM results ORDER BY start"
        ))


def plot(number: int, max_steps: int, output: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Install matplotlib: python -m pip install matplotlib") from exc
    sequence = syracuse(number, max_steps)
    fig, ax = plt.subplots()
    ax.plot(range(len(sequence)), sequence)
    ax.set(title=f"Collatz trajectory for {number}", xlabel="Step", ylabel="Value")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number", nargs="?", type=int)
    parser.add_argument("--max-steps", type=int, default=100_000)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--database", type=Path, default=Path("syracuse.sqlite3"))
    parser.add_argument("--export-csv", type=Path)
    parser.add_argument("--plot", type=Path, metavar="PNG")
    args = parser.parse_args()
    try:
        if args.start is not None or args.end is not None:
            if args.start is None or args.end is None:
                parser.error("--start and --end must be used together")
            scan(args.start, args.end, args.max_steps, args.workers,
                 args.database, args.batch_size)
        elif args.number is not None:
            sequence = syracuse(args.number, args.max_steps)
            print(*sequence, sep="\n")
            print(f"Steps: {len(sequence)-1}; Peak: {max(sequence)}")
            if args.plot:
                plot(args.number, args.max_steps, args.plot)
                print(f"Plot saved: {args.plot}")
        elif not args.export_csv:
            parser.error("Supply a number, a scan range, or --export-csv")
        if args.export_csv:
            export_csv(args.database, args.export_csv)
            print(f"CSV saved: {args.export_csv}")
    except (ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    mp.freeze_support()
    main()
