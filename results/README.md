# Collatz frontier exploration results (10 November 2026)

These files are experimental outputs from the Syracuse Rust engine, **not a certified world record**.

| File | Starting values | Status |
| --- | --- | --- |
| `frontier-1m.log` | 2392312122059207475201..2392312122059208475200 | 1m completed, 0 unresolved; included in first 100m |
| `frontier-100m.log` | 2392312122059207475201..2392312122059307475200 | 100m completed, 0 unresolved |
| `frontier-next-100m.jsonl` | 2392312122059307475201..2392312122059407475200 | 100m completed, 0 unresolved |
| `frontier-next-200m.jsonl` | 2392312122059407475201..2392312122059507475200 | 100m completed, 0 unresolved |
| `frontier-next-300m.jsonl` | 2392312122059507475201..2392312122059607475200 | 100m completed, 0 unresolved |

**Unique contiguous coverage: 400,000,000 starting values**, from 2392312122059207475201 through 2392312122059607475200 inclusive. The first 1m log overlaps the first 100m log and is **not** additional coverage.

The JSONL files contain 100 sequential one-million-number chunks each. Each row includes boundaries, completed/unresolved counts, maximum step budget, longest trajectory and highest peak in that chunk, and a flag `verified_records`. When true, the wrapper recalculated the two *reported record trajectories* using a separate Python implementation. **This does not mean all one million trajectories in that chunk were independently recalculated.** The first 100m plain-text log does not have JSONL checkpoints.

Reproduction: compile `rust/syracuse-rs` as described in `rust/README.md`, then use `rust/frontier_checkpoint.py` with the corresponding `--start`, `--count 100000000`, `--chunk 1000000`, `--workers 4`, `--max-steps 100000`, `--verify`, and a fresh `--checkpoint` file.

No per-integer trajectories or exhaustive independent verification certificates are archived here. Published frontier references may have changed and other researchers may have computed overlapping ranges.
