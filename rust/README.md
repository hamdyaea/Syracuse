# Rust engine and experimental visualizations

The Rust engine now uses a **checked u128 fast path**, exact `BigUint` overflow
fallback, compressed runs of even divisions, and Rayon parallel range scanning.
Its results are cross-checked against a straightforward arbitrary-precision
reference implementation, including values beyond 128 bits and step limits.

## Build on Manjaro

Rust 1.80+ is needed for the current Rayon dependency. This workstation has
an older default toolchain and an installed 1.88 toolchain:

```bash
cd rust
cargo +1.88.0 test
cargo +1.88.0 build --release
./target/release/syracuse-rs 27
./target/release/syracuse-rs --start 1 --end 1000000 --workers 4
```

On other machines, use a recent stable Rust toolchain and plain `cargo`.

For reproducible timing, compare equivalent ranges and step limits and
exclude Python's SQLite persistence overhead when benchmarking only the
computational engine. Rust can now write to the **existing Python-compatible results schema** with `--database`. SQLite persistence is optional; without `--database` scans remain in-memory and faster.

## Animated interactive 3D trajectories

```bash
python3 visualize3d.py 837799 --output syracuse-3d.html
python3 visualize3d.py 1104823904239754287061021 --output large-3d.html
```

Open the generated HTML in a browser. Drag to rotate, use the mouse wheel
to zoom, and adjust playback speed, spiral width and elevation. The HTML is
self-contained and works offline. Height uses log2(value); the spiral is
a **visual embedding**, not a mathematical geometric orbit.

## Experimental inverse Collatz tree

```bash
python3 inverse_tree.py --depth 12 --max-nodes 300 --output inverse-tree.svg --json inverse-tree.json
```

The inverse edges use `n -> 2n` and, when valid, `n -> (n-1)/3`.
The trivial 1-2-4 cycle is not expanded repeatedly. The result is a
finite exploration rooted at 1, not a proof that every positive integer
belongs to the tree. This experiment is independent of any unverified
claims of a complete proof.

## Remaining roadmap

- Larger-scale SQLite resume benchmarks and compatibility tests against
  existing databases containing millions of records
- Seeded random exploration in Rust, arbitrary-bit sampling and records
- Cached stopping times, adaptive chunk sizes and performance profiling
- Statistical dashboard and richer interactive visualizations
- Formal descriptions and independently testable hypotheses for alternative
  Collatz automata, including proposals attributed to Aberkane
- End-to-end reproducible benchmarks and release artifacts

**Do not delete or replace the Python databases.** The Python CLI remains
the supported persistence and visualization workflow until parity is proven.
## Progress and persistent range scans

```bash
./target/release/syracuse-rs --start 100000001 --end 200000000 --workers 4 --database syracuse.sqlite3 --batch-size 4096
```

Progress includes percent, processed values, throughput and ETA. In database
mode each committed batch survives interruption, and rerunning the command
skips completed rows. Limited rows are retried only when `--max-steps` is
increased. Database schema matches Python's `results(start,steps,peak,status,max_steps)`.
SQLite uses a signed 64-bit integer primary key: ranges must end at or below
9,223,372,036,854,775,807. For giant arbitrary precision starting values
use the Python random explorer or the single-number Rust mode.

**Database choice:** use `syracuse.sqlite3` to share and resume the existing
Python contiguous scan, or `syracuse-rust.sqlite3` to keep an independent
experiment. Both share the same schema. Keep local DBs out of GitHub.

**Important:** without `--database`, progress is displayed but results are
not saved; there is no resume capability. Progress and ETA are estimates.

## Arithmetic optimization (November 2026)

The hot path now keeps the running peak in native `u128` and converts it
to `BigUint` only once per starting value (unless an actual overflow requires
arbitrary precision). This removes repeated heap allocations during the
frequent odd steps, without changing Collatz steps or the stored peak.

On a **fresh temporary SQLite database**, a 1,000,000-integer scan over
200,000,001–201,000,000 took **2.715 s** with four workers on the development
machine. This is a single measurement, not an apples-to-apples speedup claim
against the older version; use the same range and hardware for comparisons.

To test future performance without touching your main research database:

```bash
./target/release/syracuse-rs --start 200000001 --end 201000000 \
  --workers 4 --database /tmp/syracuse-benchmark.sqlite3
```

Do not compare a fully cached SQLite rerun to a fresh scan.

## Fused odd/even fast path

For native `u128` trajectories, the engine now combines an odd `3n+1`
transition with the immediately following powers-of-two divisions. It still
counts **every original Collatz step**, records the peak **before** shifting,
and honors exact `--max-steps` boundaries. Added tests cover short step
limits and overflow around `u128::MAX`.

In a small four-worker, no-database benchmark over 210,000,001–212,000,000,
the previous version took **0.384 s** and the new version **0.281 s**
(about **27% less time**). These are single-run observations and do not
measure SQLite write throughput; repeat trials before generalizing.

## SQLite batch tuning (November 2026)

The default batch size is now **16,384**. A fresh 2-million-row SQLite
benchmark favored 16,384 over 4,096 (4.803 s vs 5.578 s in one run;
5.718 s vs 6.610 s in another run with connection tuning). SQLite's
synchronous and journal modes are **not** weakened. The connection uses a
32 MiB page cache and in-memory temporary storage. Performance depends on
disk, database size, free space and concurrent workloads. Check `df -h .`
before extending a large database.