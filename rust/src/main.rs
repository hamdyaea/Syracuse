// SPDX-License-Identifier: GPL-3.0-only
//! Exact Collatz engine: fast u128 arithmetic, BigUint overflow fallback,
//! compressed even steps, and parallel streaming range scans.
use num_bigint::BigUint;
use num_traits::{One, ToPrimitive, Zero};
use rayon::prelude::*;
use std::{env, process, time::Instant};

#[derive(Clone, Debug, PartialEq, Eq)]
struct ResultRow {
    steps: u64,
    peak: BigUint,
    status: &'static str,
}
fn analyze(start: &BigUint, max_steps: u64) -> ResultRow {
    let one = BigUint::one();
    let mut big: Option<BigUint> = None;
    let mut small = start.to_u128().unwrap_or(0);
    if start.to_u128().is_none() {
        big = Some(start.clone());
    }
    let mut peak = start.clone();
    let mut steps = 0u64;
    while steps < max_steps {
        if let Some(n) = big.as_mut() {
            if *n == one {
                break;
            }
            if (&*n & &one).is_zero() {
                *n >>= 1usize;
                steps += 1;
            } else {
                *n = &*n * 3u8 + &one;
                steps += 1;
                if *n > peak {
                    peak = n.clone();
                }
            }
            if let Some(value) = n.to_u128() {
                small = value;
                big = None;
            }
        } else {
            if small == 1 {
                break;
            }
            if small & 1 == 0 {
                let shift = (small.trailing_zeros() as u64).min(max_steps - steps) as u32;
                small >>= shift;
                steps += shift as u64;
            } else if let Some(next) = small.checked_mul(3).and_then(|n| n.checked_add(1)) {
                small = next;
                steps += 1;
                if BigUint::from(small) > peak {
                    peak = BigUint::from(small);
                }
            } else {
                let next = BigUint::from(small) * 3u8 + &one;
                steps += 1;
                if next > peak {
                    peak = next.clone();
                }
                big = Some(next);
            }
        }
    }
    let reached = big.as_ref().map_or(small == 1, |n| *n == one);
    ResultRow {
        steps,
        peak,
        status: if reached { "reached_1" } else { "limit" },
    }
}
fn parse_number(s: &str) -> BigUint {
    let n = BigUint::parse_bytes(s.as_bytes(), 10).unwrap_or_else(|| {
        eprintln!("Invalid positive integer: {s}");
        process::exit(2)
    });
    if n.is_zero() {
        eprintln!("Number must be positive");
        process::exit(2);
    }
    n
}
#[derive(Default)]
struct Summary {
    completed: u64,
    unresolved: u64,
    longest: Option<(u64, u64)>,
    highest: Option<(BigUint, u64)>,
}
impl Summary {
    fn add(&mut self, n: u64, r: ResultRow) {
        if r.status != "reached_1" {
            self.unresolved += 1;
            return;
        }
        self.completed += 1;
        if self.longest.map_or(true, |(steps, start)| {
            r.steps > steps || (r.steps == steps && n < start)
        }) {
            self.longest = Some((r.steps, n));
        }
        if self.highest.as_ref().map_or(true, |(peak, start)| {
            r.peak > *peak || (r.peak == *peak && n < *start)
        }) {
            self.highest = Some((r.peak, n));
        }
    }
    fn merge(mut self, other: Self) -> Self {
        self.completed += other.completed;
        self.unresolved += other.unresolved;
        if let Some((steps, n)) = other.longest {
            if self
                .longest
                .map_or(true, |(s, k)| steps > s || (steps == s && n < k))
            {
                self.longest = Some((steps, n));
            }
        }
        if let Some((peak, n)) = other.highest {
            if self
                .highest
                .as_ref()
                .map_or(true, |(p, k)| peak > *p || (peak == *p && n < *k))
            {
                self.highest = Some((peak, n));
            }
        }
        self
    }
}
fn scan(lo: u64, hi: u64, max_steps: u64, workers: usize) -> Summary {
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(workers)
        .build()
        .expect("thread pool");
    pool.install(|| {
        // Chunks bound task overhead without allocating a vector of input integers.
        let chunks = (hi - lo) / 4096 + 1;
        (0..chunks)
            .into_par_iter()
            .map(|i| {
                let first = lo + i * 4096;
                let last = hi.min(first.saturating_add(4095));
                let mut s = Summary::default();
                for n in first..=last {
                    s.add(n, analyze(&BigUint::from(n), max_steps));
                }
                s
            })
            .reduce(Summary::default, Summary::merge)
    })
}
fn usage() {
    eprintln!("Usage: syracuse-rs NUMBER [--max-steps N]");
    eprintln!("       syracuse-rs --start N --end N [--workers N] [--max-steps N]");
}
fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut number = None;
    let mut start = None;
    let mut end = None;
    let mut max_steps = 100_000u64;
    let mut workers = std::thread::available_parallelism().map_or(1, |n| n.get());
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--max-steps" | "--start" | "--end" | "--workers" => {
                if i + 1 >= args.len() {
                    usage();
                    process::exit(2);
                }
                let value = args[i + 1].parse::<u64>().unwrap_or_else(|_| {
                    usage();
                    process::exit(2);
                });
                match args[i].as_str() {
                    "--max-steps" => max_steps = value,
                    "--start" => start = Some(value),
                    "--end" => end = Some(value),
                    _ => workers = usize::try_from(value).unwrap_or(0),
                }
                i += 2;
            }
            x if !x.starts_with('-') && number.is_none() => {
                number = Some(parse_number(x));
                i += 1;
            }
            _ => {
                usage();
                process::exit(2);
            }
        }
    }
    if max_steps == 0 || workers == 0 {
        usage();
        process::exit(2);
    }
    match (number, start, end) {
        (Some(n), None, None) => {
            let r = analyze(&n, max_steps);
            println!(
                "start={n} steps={} peak={} status={}",
                r.steps, r.peak, r.status
            );
        }
        (None, Some(lo), Some(hi)) if lo > 0 && lo <= hi => {
            let t = Instant::now();
            let r = scan(lo, hi, max_steps, workers);
            println!(
                "range={lo}..={hi} completed={} unresolved={} workers={workers} elapsed={:.3}s",
                r.completed,
                r.unresolved,
                t.elapsed().as_secs_f64()
            );
            if let Some((steps, n)) = r.longest {
                println!("longest_steps={steps} start={n}");
            }
            if let Some((peak, n)) = r.highest {
                println!("highest_peak={peak} start={n}");
            }
        }
        _ => {
            usage();
            process::exit(2);
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn reference(start: &BigUint, max_steps: u64) -> ResultRow {
        let mut n = start.clone();
        let mut peak = n.clone();
        let mut steps = 0;
        while n != BigUint::one() && steps < max_steps {
            if (&n & BigUint::one()).is_zero() {
                n >>= 1usize;
            } else {
                n = n * 3u8 + 1u8;
            }
            if n > peak {
                peak = n.clone();
            }
            steps += 1;
        }
        ResultRow {
            steps,
            peak,
            status: if n == BigUint::one() {
                "reached_1"
            } else {
                "limit"
            },
        }
    }
    #[test]
    fn known_values() {
        let r = analyze(&BigUint::from(27u32), 1000);
        assert_eq!(r.steps, 111);
        assert_eq!(r.peak, BigUint::from(9232u32));
        assert_eq!(r.status, "reached_1");
        assert_eq!(analyze(&BigUint::one(), 100).steps, 0);
    }
    #[test]
    fn limits_and_large_values() {
        for bits in [1, 63, 127, 128, 129, 256] {
            let n = (BigUint::one() << bits) + 7u8;
            for limit in [1, 2, 7, 200] {
                assert_eq!(analyze(&n, limit), reference(&n, limit));
            }
        }
    }
    #[test]
    fn exhaustive_parity() {
        for n in 1..=10000u64 {
            let n = BigUint::from(n);
            assert_eq!(analyze(&n, 10000), reference(&n, 10000));
        }
    }
    #[test]
    fn parallel_parity() {
        let a = scan(1, 10000, 10000, 1);
        let b = scan(1, 10000, 10000, 4);
        assert_eq!(
            (a.completed, a.unresolved, a.longest, a.highest),
            (b.completed, b.unresolved, b.longest, b.highest)
        );
    }
}