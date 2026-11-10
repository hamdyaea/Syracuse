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
computational engine. Rust's current scan does **not** write results to SQLite.

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

- SQLite compatibility and resume for Rust, with migration tests against
  existing databases containing millions of records
- Seeded random exploration in Rust, arbitrary-bit sampling and records
- Cached stopping times, adaptive chunk sizes and performance profiling
- Statistical dashboard and richer interactive visualizations
- Formal descriptions and independently testable hypotheses for alternative
  Collatz automata, including proposals attributed to Aberkane
- End-to-end reproducible benchmarks and release artifacts

**Do not delete or replace the Python databases.** The Python CLI remains
the supported persistence and visualization workflow until parity is proven.