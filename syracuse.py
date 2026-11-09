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


def _worker(job: tuple[int, int]) -> tuple[int, int, int, str]:
    return analyze(*job)


def init_db(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS results (
        start INTEGER PRIMARY KEY, steps INTEGER NOT NULL,
        peak TEXT NOT NULL, status TEXT NOT NULL,
        max_steps INTEGER NOT NULL)""")
    connection.execute("CREATE INDEX IF NOT EXISTS results_status ON results(status)")
    connection.commit()


def scan(start: int, end: int, max_steps: int, workers: int,
         database: Path, batch_size: int = 1000) -> None:
    if not 1 <= start <= end or max_steps < 1 or workers < 1 or batch_size < 1:
        raise ValueError("Invalid scan parameters")
    if end > 2**63 - 1:
        raise ValueError("SQLite INTEGER start keys must fit signed 64-bit")
    connection = sqlite3.connect(database)
    try:
        init_db(connection)
        # Only reuse completed rows, or incomplete rows computed with at least
        # the current step limit. Raising the limit retries unresolved rows.
        def pending():
            # Pool.imap consumes its input in a feeder thread. Create the
            # read-only connection inside that thread, never share the writer.
            reader = sqlite3.connect(database, timeout=30)
            try:
                for n in range(start, end + 1):
                    row = reader.execute(
                        "SELECT status, max_steps FROM results WHERE start=?", (n,)
                    ).fetchone()
                    if row is None or (row[0] == "limit" and row[1] < max_steps):
                        yield n, max_steps
            finally:
                reader.close()

        started = time.monotonic()
        count = 0
        best_steps = (-1, 0)
        best_peak = (-1, 0)
        def consume(iterator):
            nonlocal count, best_steps, best_peak
            buffer = []
            for n, steps, peak, status in iterator:
                buffer.append((n, steps, str(peak), status, max_steps))
                count += 1
                if status == "reached_1":
                    if steps > best_steps[0]:
                        best_steps = (steps, n)
                    if peak > best_peak[0]:
                        best_peak = (peak, n)
                if len(buffer) >= batch_size:
                    connection.executemany(
                        "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?)", buffer
                    )
                    connection.commit()
                    buffer.clear()
                    print(f"Processed {count:,} new values in "
                          f"{time.monotonic()-started:.1f}s", flush=True)
            if buffer:
                connection.executemany(
                    "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?)", buffer
                )
                connection.commit()

        if workers == 1:
            consume(map(_worker, pending()))
        else:
            # Pool feeder thread owns its SQLite reader; main thread owns writer.
            # imap streams results; chunksize amortizes process IPC overhead.
            with mp.Pool(workers) as pool:
                consume(pool.imap(_worker, pending(), chunksize=100))
        total = connection.execute(
            "SELECT COUNT(*) FROM results WHERE start BETWEEN ? AND ?",
            (start, end),
        ).fetchone()[0]
        unresolved = connection.execute(
            "SELECT COUNT(*) FROM results WHERE start BETWEEN ? AND ? "
            "AND status != 'reached_1'", (start, end),
        ).fetchone()[0]
        print(f"Stored: {total:,} | Unresolved: {unresolved:,} "
              f"| New: {count:,} | Elapsed: {time.monotonic()-started:.2f}s")
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
