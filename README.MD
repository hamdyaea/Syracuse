# Syracuse / Collatz Research Engine

**Developer:** Hamdy Abou El Anein  
**Contact:** info@daylightlinux.ch  
**License:** GPL-3.0-only

A Python 3 research CLI for exploring the **Collatz conjecture**, also known as the **Syracuse conjecture** or **3n + 1 problem**.

**Learn about the conjecture:** [Wikipedia (French): Conjecture de Syracuse](https://fr.wikipedia.org/wiki/Conjecture_de_Syracuse) · [Wikipedia (English): Collatz conjecture](https://en.wikipedia.org/wiki/Collatz_conjecture)

The conjecture states that every positive integer eventually reaches 1 when even numbers are divided by 2 and odd numbers are replaced with `3n + 1`. This has **not been proven** for all positive integers. Computational checks do not constitute a mathematical proof.

## Features

- Exact integer arithmetic; original, uncompressed Collatz step counts
- Single-number sequences and optional PNG trajectory plots
- Parallel range scanning using multiple CPU processes
- Per-batch memoization of completed trajectories (stopping time and maximum)
- Indexed, batched SQLite lookups instead of one query per starting integer
- SQLite checkpoints and automatic resume of completed calculations
- Distinguishes `reached_1`, `limit`, and `cycle`
- CSV export and automated tests

## Requirements

- Python 3.10+ (standard library for scanning, saving and exporting)
- Optional: Matplotlib for plotting: `python3 -m pip install matplotlib`

## Installation

```bash
git clone https://github.com/hamdyaea/Syracuse.git
cd Syracuse
python3 -m unittest discover -s tests -v
```

## Usage examples

### Display a sequence

```bash
python3 syracuse.py 27
python3 syracuse.py 27 --max-steps 1000
```

### Create a trajectory graph (PNG)

```bash
python3 -m pip install matplotlib
python3 syracuse.py 27 --plot collatz-27.png
python3 syracuse.py 837799 --plot collatz-837799.png
```

The generated image shows the starting value's trajectory, step by step, until 1. Plotting is optional; no graphical desktop is required because Matplotlib uses the noninteractive Agg backend.

### Scan 1 million integers on 4 CPU processes

```bash
python3 syracuse.py --start 1 --end 1000000 --workers 4
```

### Extend the scan to 10 million, resuming existing results

```bash
python3 syracuse.py --start 1 --end 10000000 --workers 4 \
  --database syracuse.sqlite3 --batch-size 5000
```

Existing completed rows in the database are skipped. Increasing `--max-steps` retries rows previously marked `limit`. Batch size controls SQLite lookup/write granularity and the amount of work reprocessed after interruption. Try `1000` (default) or `5000` and benchmark on your own hardware.

### Export stored results to CSV

```bash
python3 syracuse.py --database syracuse.sqlite3 --export-csv results.csv
```

CSV columns: `start,steps,peak,status,max_steps`. Peak values are stored as text to preserve large integer precision.

### Test a smaller limit

```bash
python3 syracuse.py --start 1 --end 10000 --workers 2 \
  --max-steps 100 --database limited.sqlite3
```

A `limit` result means the configured step budget was exhausted, **not** that a counterexample has been discovered. A `cycle` result indicates a repeated value before reaching 1.

## Example results

A sample run on positive integers from 1 through 1,000,000 reported:

| Metric | Result |
|---|---:|
| Starting integers checked | 1,000,000 |
| Unresolved | 0 |
| Longest stopping time | 524 steps (837799) |
| Highest peak | 56,991,483,520 (704511) |
| Runtime before the batching optimization | 49.68 seconds with 4 workers |

These are example results from a user run, **not** a performance guarantee or a benchmark of the optimized implementation.

## Performance and correctness

The parallel engine sends batches of starting integers to worker processes, memoizes only tails already known to reach 1, and stores each batch transactionally. This reduces SQLite query overhead and repeated Collatz arithmetic. Actual speedups depend on CPU, database, batch size and the range being tested.

The program stores start values in SQLite's signed 64-bit INTEGER column; starting values must be at most `2**63 - 1`. Intermediate Collatz values use Python's arbitrary-precision integers.

Run the test suite after upgrades:

```bash
python3 -m unittest discover -s tests -v
```

## License and history

GPL-3.0-only. Original version preserved in the [old branch](https://github.com/hamdyaea/Syracuse/tree/old).
