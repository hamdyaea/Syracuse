# Syracuse / Collatz Research Engine

**Developer:** Hamdy Abou El Anein  
**Contact:** info@daylightlinux.ch  
**License:** GPL-3.0-only

Explore the Collatz conjecture with exact Python integer arithmetic. The conjecture is **unproven**; reaching a step limit is not a counterexample.

## Usage

```bash
python3 syracuse.py 27
python3 syracuse.py 27 --plot collatz-27.png  # optional matplotlib
python3 syracuse.py --start 1 --end 1000000 --workers 4
python3 syracuse.py --start 1 --end 1000000 --workers 4 --database results.sqlite3
python3 syracuse.py --database results.sqlite3 --export-csv results.csv
python3 -m unittest discover -s tests -v
```

The SQLite database stores each starting value, stopping time, peak (as text to avoid integer overflow), status, and step limit. Scans resume by skipping completed values. If you increase `--max-steps`, previously limited trajectories are retried. Results are committed in batches, so at most the last uncommitted batch is lost on interruption.

`--workers` uses separate processes for parallel calculation. A large range may be slow and consume significant disk space; start with a small range. SQLite start keys are restricted to signed 64-bit integers. The original single-number CLI remains compatible. PNG plotting requires `matplotlib`; all other functionality uses the standard library.

Original implementation: [old branch](https://github.com/hamdyaea/Syracuse/tree/old).
