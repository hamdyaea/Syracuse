#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Explore Collatz trajectories and discover local records, not global proofs."""
from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import random
import sqlite3
import time
from pathlib import Path

from syracuse import analyze, syracuse


def sample_numbers(count: int, bits: int, seed: int):
    """Deterministic, positive, exactly bits-bit starting integers."""
    if count < 1 or bits < 1:
        raise ValueError("count and bits must be positive")
    rng = random.Random(seed)
    for _ in range(count):
        yield rng.getrandbits(bits - 1) | (1 << (bits - 1))


def _analyze_job(job):
    return analyze(*job)


def explore(count: int, bits: int, seed: int, max_steps: int,
            workers: int, database: Path, batch_size: int = 1000):
    if min(count, bits, max_steps, workers, batch_size) < 1:
        raise ValueError("count, bits, max_steps, workers and batch_size must be positive")
    connection = sqlite3.connect(database)
    try:
        connection.execute("""CREATE TABLE IF NOT EXISTS samples (
            start TEXT PRIMARY KEY, steps INTEGER NOT NULL, peak TEXT NOT NULL,
            status TEXT NOT NULL, max_steps INTEGER NOT NULL)""")
        connection.commit()
        started = time.monotonic()
        inserted = 0
        best_steps = (-1, 0)
        best_peak = (-1, 0)

        def jobs():
            # This iterator is consumed by a Pool feeder thread when parallel.
            # Own the SQLite reader in that thread; the writer stays in main.
            reader = sqlite3.connect(database, timeout=30)
            try:
                for n in sample_numbers(count, bits, seed):
                    row = reader.execute(
                        "SELECT status, max_steps FROM samples WHERE start=?",
                        (str(n),)
                    ).fetchone()
                    if row is None or (row[0] == "limit" and row[1] < max_steps):
                        yield (n, max_steps)
            finally:
                reader.close()

        def consume(results):
            nonlocal inserted, best_steps, best_peak
            batch = []
            for n, steps, peak, status in results:
                batch.append((str(n), steps, str(peak), status, max_steps))
                if status == "reached_1":
                    if steps > best_steps[0]:
                        best_steps = (steps, n)
                    if peak > best_peak[0]:
                        best_peak = (peak, n)
                if len(batch) >= batch_size:
                    connection.executemany(
                        "INSERT INTO samples VALUES (?,?,?,?,?) "
                        "ON CONFLICT(start) DO UPDATE SET "
                        "steps=excluded.steps, peak=excluded.peak, "
                        "status=excluded.status, max_steps=excluded.max_steps "
                        "WHERE samples.status='limit' AND "
                        "samples.max_steps < excluded.max_steps", batch)
                    connection.commit()
                    inserted += len(batch)
                    batch.clear()
                    print(f"Evaluated {inserted:,} samples in "
                          f"{time.monotonic()-started:.1f}s", flush=True)
            if batch:
                connection.executemany(
                    "INSERT INTO samples VALUES (?,?,?,?,?) "
                    "ON CONFLICT(start) DO UPDATE SET "
                    "steps=excluded.steps, peak=excluded.peak, "
                    "status=excluded.status, max_steps=excluded.max_steps "
                    "WHERE samples.status='limit' AND "
                    "samples.max_steps < excluded.max_steps", batch)
                connection.commit()
                inserted += len(batch)

        if workers == 1:
            consume(map(_analyze_job, jobs()))
        else:
            with mp.Pool(workers) as pool:
                consume(pool.imap(_analyze_job, jobs(), chunksize=100))
        completed, limited, cycles = connection.execute(
            "SELECT SUM(status='reached_1'), SUM(status='limit'), "
            "SUM(status='cycle') FROM samples"
        ).fetchone()
        print(f"Database: {database} | Unique samples: "
              f"{connection.execute('SELECT COUNT(*) FROM samples').fetchone()[0]:,}")
        print(f"Reached 1: {completed or 0:,} | Step limit: {limited or 0:,} "
              f"| Cycles: {cycles or 0:,}")
        print(f"Best completed stopping time in this run: {best_steps}")
        print(f"Highest completed peak in this run: {best_peak}")
        print(f"Elapsed: {time.monotonic()-started:.2f}s")
    finally:
        connection.close()


def records(database: Path, csv_path: Path | None = None):
    """Report records among saved samples, using Python big integers."""
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT start, steps, peak FROM samples WHERE status='reached_1'"
        )
        best_steps = (-1, 0)
        best_peak = (-1, 0)
        for n, steps, peak in rows:
            n, peak = int(n), int(peak)
            if steps > best_steps[0]:
                best_steps = (steps, n)
            if peak > best_peak[0]:
                best_peak = (peak, n)
    print(f"Longest completed trajectory: {best_steps}")
    print(f"Highest peak: {best_peak}")
    if csv_path:
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("metric", "value", "starting_number"))
            writer.writerow(("longest_steps", *best_steps))
            writer.writerow(("highest_peak", *best_peak))
    return best_steps, best_peak


def plot_records(database: Path, destination: Path, max_steps: int):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Install matplotlib to generate graphs") from exc
    longest, highest = records(database)
    starts = list(dict.fromkeys([longest[1], highest[1]]))
    if not all(n > 0 for n in starts):
        raise ValueError("No completed samples to plot")
    fig, axes = plt.subplots(len(starts), 1, figsize=(11, 4 * len(starts)),
                             squeeze=False)
    for ax, n in zip(axes[:, 0], starts):
        seq = syracuse(n, max_steps)
        ax.plot(range(len(seq)), seq, linewidth=1)
        ax.set_title(f"Starting number: {n} ({len(seq)-1} steps)")
        ax.set_xlabel("Step")
        ax.set_ylabel("Value")
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--bits", type=int, default=80)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--max-steps", type=int, default=100000)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--database", type=Path, default=Path("syracuse-explore.sqlite3"))
    parser.add_argument("--records-only", action="store_true")
    parser.add_argument("--export-records", type=Path)
    parser.add_argument("--plot-records", type=Path)
    args = parser.parse_args()
    try:
        if not args.records_only:
            explore(args.count, args.bits, args.seed, args.max_steps,
                    args.workers, args.database, args.batch_size)
        if args.records_only or args.export_records or args.plot_records:
            records(args.database, args.export_records)
        if args.plot_records:
            plot_records(args.database, args.plot_records, args.max_steps)
    except (ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    mp.freeze_support()
    main()
