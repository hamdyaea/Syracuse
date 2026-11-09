// SPDX-License-Identifier: GPL-3.0-only
//! Native Collatz exploration. Exact BigUint arithmetic, no overflow.
use num_bigint::BigUint;
use num_traits::{One, Zero};
use std::{env, process, time::Instant};

#[derive(Debug, PartialEq, Eq)]
struct ResultRow {
    steps: u64,
    peak: BigUint,
    status: &'static str,
}

fn analyze(start: &BigUint, max_steps: u64) -> ResultRow {
    let one = BigUint::one();
    let mut n = start.clone();
    let mut peak = n.clone();
    let mut steps = 0;
    // A bounded run returns "limit", never a false counterexample.
    while n != one && steps < max_steps {
        if (&n & &one).is_zero() {
            n >>= 1usize;
        } else {
            n = &n * 3u8 + &one;
        }
        if n > peak { peak = n.clone(); }
        steps += 1;
    }
    ResultRow { steps, peak, status: if n == one { "reached_1" } else { "limit" } }
}

fn parse_number(s: &str) -> BigUint {
    let n = BigUint::parse_bytes(s.as_bytes(), 10)
        .unwrap_or_else(|| { eprintln!("Invalid positive integer: {s}"); process::exit(2) });
    if n.is_zero() { eprintln!("Number must be positive"); process::exit(2); }
    n
}

fn usage() {
    eprintln!("Usage: syracuse-rs NUMBER [--max-steps N]");
    eprintln!("       syracuse-rs --start N --end N [--max-steps N]");
    eprintln!("Exact arbitrary-precision Collatz computation; bounded runs are not proofs.");
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut number: Option<BigUint> = None;
    let mut start: Option<u64> = None;
    let mut end: Option<u64> = None;
    let mut max_steps = 100_000u64;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--max-steps" | "--start" | "--end" => {
                if i + 1 >= args.len() { usage(); process::exit(2); }
                let value = args[i + 1].parse::<u64>()
                    .unwrap_or_else(|_| { usage(); process::exit(2); });
                match args[i].as_str() {
                    "--max-steps" => max_steps = value,
                    "--start" => start = Some(value),
                    _ => end = Some(value),
                }
                i += 2;
            }
            x if !x.starts_with('-') && number.is_none() => {
                number = Some(parse_number(x));
                i += 1;
            }
            _ => { usage(); process::exit(2); }
        }
    }
    if max_steps == 0 { usage(); process::exit(2); }
    match (number, start, end) {
        (Some(n), None, None) => {
            let r = analyze(&n, max_steps);
            println!("start={n} steps={} peak={} status={}", r.steps, r.peak, r.status);
        }
        (None, Some(lo), Some(hi)) if lo > 0 && lo <= hi => {
            let t = Instant::now();
            let mut completed = 0u64;
            let mut unresolved = 0u64;
            let mut longest: Option<(u64, u64)> = None;
            let mut highest: Option<(BigUint, u64)> = None;
            for n in lo..=hi {
                let r = analyze(&BigUint::from(n), max_steps);
                if r.status == "reached_1" {
                    completed += 1;
                    if longest.map_or(true, |(steps, _)| r.steps > steps) {
                        longest = Some((r.steps, n));
                    }
                    if highest.as_ref().map_or(true, |(peak, _)| &r.peak > peak) {
                        highest = Some((r.peak, n));
                    }
                } else { unresolved += 1; }
            }
            println!("range={lo}..={hi} completed={completed} unresolved={unresolved} elapsed={:.3}s", t.elapsed().as_secs_f64());
            if let Some((steps, n)) = longest { println!("longest_steps={steps} start={n}"); }
            if let Some((peak, n)) = highest { println!("highest_peak={peak} start={n}"); }
        }
        _ => { usage(); process::exit(2); }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn known_values() {
        let r = analyze(&BigUint::from(27u32), 1000);
        assert_eq!(r.steps, 111);
        assert_eq!(r.peak, BigUint::from(9232u32));
        assert_eq!(r.status, "reached_1");
        assert_eq!(analyze(&BigUint::one(), 100).steps, 0);
    }
    #[test]
    fn step_limit() {
        let r = analyze(&BigUint::from(27u32), 1);
        assert_eq!(r.steps, 1);
        assert_eq!(r.status, "limit");
    }
    #[test]
    fn large_integers_do_not_overflow() {
        let n = (BigUint::one() << 256usize) - BigUint::one();
        let r = analyze(&n, 1);
        assert_eq!(r.status, "limit");
        assert!(r.peak > n);
    }
}
