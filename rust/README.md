# Syracuse Rust engine (experimental)

This is the **first migration stage**, not a replacement for the Python application.
It uses exact `num-bigint::BigUint` arithmetic to avoid overflow, including for starting
values larger than 128 bits. A step-limit result is *not* a counterexample.

## Build and test

```bash
cd rust
cargo test
cargo build --release
./target/release/syracuse-rs 27
./target/release/syracuse-rs --start 1 --end 1000000
./target/release/syracuse-rs 1104823904239754287061021
```

The initial engine supports single-number and sequential range calculations. It
reports the longest completed trajectory and highest peak in the requested range.

**Not yet migrated:** SQLite persistence/resume, parallel Rayon execution, cached
stopping times, seeded random exploration, CSV export and plotting. Continue using
the Python CLI for those features. Do not compare timings without controlling
the input range, CPU and persistence settings.

Planned next stages: parity tests against Python, Rayon parallelism, fast u64/u128
path with checked arithmetic and BigUint fallback, SQLite compatibility, and a
unified Python plotting interface.
