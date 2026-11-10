// SPDX-License-Identifier: GPL-3.0-only
//! Exact Collatz engine: fast u128 arithmetic, BigUint overflow fallback,
//! compressed even steps, and parallel streaming range scans.
use num_bigint::BigUint;
use num_traits::{One, ToPrimitive, Zero};
use rayon::prelude::*;
use rusqlite::{params, Connection};
use std::io::{self, IsTerminal, Write};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::{env, process, time::Instant};

#[derive(Clone, Debug, PartialEq, Eq)]
struct ResultRow {
    steps: u64,
    peak: BigUint,
    status: &'static str,
}
fn analyze(start: &BigUint, max_steps: u64) -> ResultRow {
    let mut big: Option<BigUint> = None;
    let mut small = start.to_u128().unwrap_or(0);
    if start.to_u128().is_none() {
        big = Some(start.clone());
    }
    // Keep the peak in u128 until an actual overflow, avoiding BigUint
    // allocations and conversions on every odd step.
    let mut peak_small = small;
    let mut peak_big: Option<BigUint> = big.clone();
    let mut steps = 0u64;
    while steps < max_steps {
        if let Some(n) = big.as_mut() {
            if *n == BigUint::one() {
                break;
            }
            if (n.bit(0)) == false {
                *n >>= 1usize;
            } else {
                *n = &*n * 3u8 + 1u8;
                if peak_big.as_ref().is_none_or(|peak| *n > *peak) {
                    peak_big = Some(n.clone());
                }
            }
            steps += 1;
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
                // Every 3n+1 is even. Consume the odd step and the following
                // divisions together, but count each original Collatz step.
                if peak_big.is_none() && next > peak_small {
                    peak_small = next;
                }
                let remaining_even = max_steps - steps - 1;
                let shift = (next.trailing_zeros() as u64).min(remaining_even) as u32;
                small = next >> shift;
                steps += 1 + shift as u64;
            } else {
                let next = BigUint::from(small) * 3u8 + 1u8;
                steps += 1;
                if peak_big.as_ref().is_none_or(|peak| next > *peak) {
                    peak_big = Some(next.clone());
                }
                big = Some(next);
            }
        }
    }
    let reached = big.as_ref().map_or(small == 1, |n| *n == BigUint::one());
    ResultRow {
        steps,
        peak: peak_big.unwrap_or_else(|| BigUint::from(peak_small)),
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
    let done = AtomicU64::new(0);
    let started = Instant::now();
    let display = Mutex::new(Progress::new());
    let total = hi - lo + 1;
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
                let completed =
                    done.fetch_add(last - first + 1, Ordering::Relaxed) + last - first + 1;
                if let Ok(mut display) = display.lock() {
                    display.update(completed, total, started);
                }
                s
            })
            .reduce(Summary::default, Summary::merge)
    })
}

// Published verification frontier is configurable: never claim an independent
// world record from exploratory trajectories.
fn frontier() -> BigUint {
    BigUint::from(2075u32) << 60usize
}
fn scan_big(
    lo: &BigUint,
    hi: &BigUint,
    max_steps: u64,
    workers: usize,
) -> Result<(), Box<dyn std::error::Error>> {
    let count = (hi - lo + BigUint::one())
        .to_u64()
        .ok_or("range contains more than u64::MAX values; split it into smaller windows")?;
    if count == 0 {
        return Err("empty range".into());
    }
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(workers)
        .build()?;
    let started = Instant::now();
    let done = AtomicU64::new(0);
    let progress = Mutex::new(Progress::new());
    let chunks = (count - 1) / 4096 + 1;
    let (completed, unresolved, longest, highest) = pool.install(|| {
        (0..chunks)
            .into_par_iter()
            .map(|i| {
                let offset = i * 4096;
                let length = 4096u64.min(count - offset);
                let mut n = lo + offset;
                let mut completed = 0u64;
                let mut unresolved = 0u64;
                let mut longest: Option<(u64, BigUint)> = None;
                let mut highest: Option<(BigUint, BigUint)> = None;
                for _ in 0..length {
                    let r = analyze(&n, max_steps);
                    if r.status == "reached_1" {
                        completed += 1;
                        if longest.as_ref().is_none_or(|(steps, start)| {
                            r.steps > *steps || (r.steps == *steps && n < *start)
                        }) {
                            longest = Some((r.steps, n.clone()));
                        }
                        if highest.as_ref().is_none_or(|(peak, start)| {
                            r.peak > *peak || (r.peak == *peak && n < *start)
                        }) {
                            highest = Some((r.peak, n.clone()));
                        }
                    } else {
                        unresolved += 1;
                    }
                    n += 1u8;
                }
                let current = done.fetch_add(length, Ordering::Relaxed) + length;
                if let Ok(mut display) = progress.lock() {
                    display.update(current, count, started);
                }
                (completed, unresolved, longest, highest)
            })
            .reduce(
                || (0, 0, None, None),
                |a, b| {
                    let longest = match (a.2, b.2) {
                        (Some(x), Some(y)) => Some(if x.0 > y.0 || (x.0 == y.0 && x.1 < y.1) {
                            x
                        } else {
                            y
                        }),
                        (Some(x), None) | (None, Some(x)) => Some(x),
                        _ => None,
                    };
                    let highest = match (a.3, b.3) {
                        (Some(x), Some(y)) => Some(if x.0 > y.0 || (x.0 == y.0 && x.1 < y.1) {
                            x
                        } else {
                            y
                        }),
                        (Some(x), None) | (None, Some(x)) => Some(x),
                        _ => None,
                    };
                    (a.0 + b.0, a.1 + b.1, longest, highest)
                },
            )
    });
    println!("range={lo}..={hi} completed={completed} unresolved={unresolved} workers={workers} elapsed={:.3}s", started.elapsed().as_secs_f64());
    if let Some((steps, start)) = longest {
        println!("longest_steps={steps} start={start}");
    }
    if let Some((peak, start)) = highest {
        println!("highest_peak={peak} start={start}");
    }
    println!("mode=exploration persistence=none proof_of_world_record=false");
    Ok(())
}
/// Throttle terminal output; use normal newline-delimited logs when stderr is redirected.
struct Progress {
    last: Option<Instant>,
    terminal: bool,
}
impl Progress {
    fn new() -> Self {
        Self {
            last: None,
            terminal: io::stderr().is_terminal(),
        }
    }
    fn update(&mut self, done: u64, total: u64, started: Instant) {
        let now = Instant::now();
        if done != total
            && self
                .last
                .is_some_and(|last| now.duration_since(last).as_secs_f64() < 1.0)
        {
            return;
        }
        self.last = Some(now);
        let fraction = done as f64 / total as f64;
        let filled = (fraction * 32.0).round() as usize;
        let elapsed = started.elapsed().as_secs_f64();
        let rate = if elapsed > 0.0 {
            done as f64 / elapsed
        } else {
            0.0
        };
        let eta = if rate > 0.0 {
            (total - done) as f64 / rate
        } else {
            0.0
        };
        let prefix = if self.terminal { "\r" } else { "" };
        let suffix = if self.terminal && done != total {
            ""
        } else {
            "\n"
        };
        eprint!(
            "{prefix}[{}{}] {:6.2}% {:>12}/{:<12} {:>9.0}/s ETA {:>7.1}s{suffix}",
            "#".repeat(filled.min(32)),
            "-".repeat(32 - filled.min(32)),
            fraction * 100.0,
            done,
            total,
            rate,
            eta
        );
        let _ = io::stderr().flush();
    }
}
fn scan_db(
    lo: u64,
    hi: u64,
    max_steps: u64,
    workers: usize,
    path: &str,
    batch_size: u64,
) -> Result<Summary, Box<dyn std::error::Error>> {
    if hi > i64::MAX as u64 {
        return Err("SQLite INTEGER start cannot exceed i64::MAX".into());
    }
    let mut db = Connection::open(path)?;
    db.busy_timeout(std::time::Duration::from_secs(30))?;
    // Connection-local tuning: does not weaken SQLite durability settings.
    db.execute_batch("PRAGMA cache_size=-32768; PRAGMA temp_store=MEMORY;")?;
    db.execute_batch(
        "CREATE TABLE IF NOT EXISTS results (
        start INTEGER PRIMARY KEY, steps INTEGER NOT NULL,
        peak TEXT NOT NULL, status TEXT NOT NULL, max_steps INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS results_status ON results(status);",
    )?;
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(workers)
        .build()?;
    let started = Instant::now();
    let total = hi - lo + 1;
    let mut visited = 0u64;
    let mut computed = 0u64;
    let mut summary = Summary::default();
    let mut display = Progress::new();
    let mut first = lo;
    loop {
        let last = hi.min(first.saturating_add(batch_size - 1));
        let mut known = std::collections::HashMap::new();
        {
            let mut stmt = db.prepare(
                "SELECT start,status,max_steps FROM results WHERE start BETWEEN ?1 AND ?2",
            )?;
            let rows = stmt.query_map(params![first as i64, last as i64], |row| {
                Ok((
                    row.get::<_, i64>(0)? as u64,
                    row.get::<_, String>(1)? == "limit",
                    row.get::<_, i64>(2)?,
                ))
            })?;
            for row in rows {
                let (n, status, limit) = row?;
                known.insert(n, (status, limit));
            }
        }
        let pending: Vec<u64> = (first..=last)
            .filter(|n| match known.get(n) {
                None => true,
                Some((limited, limit)) => *limited && *limit < max_steps as i64,
            })
            .collect();
        let rows: Vec<(u64, ResultRow)> = pool.install(|| {
            pending
                .par_iter()
                .map(|&n| (n, analyze(&BigUint::from(n), max_steps)))
                .collect()
        });
        if !rows.is_empty() {
            let tx = db.transaction()?;
            {
                let mut insert = tx.prepare_cached("INSERT OR REPLACE INTO results(start,steps,peak,status,max_steps) VALUES (?1,?2,?3,?4,?5)")?;
                for (n, r) in &rows {
                    insert.execute(params![
                        *n as i64,
                        r.steps as i64,
                        r.peak.to_string(),
                        r.status,
                        max_steps as i64
                    ])?;
                }
            }
            tx.commit()?;
        }
        for (n, r) in rows {
            summary.add(n, r);
            computed += 1;
        }
        visited += last - first + 1;
        display.update(visited, total, started);
        if last == hi {
            break;
        }
        first = last + 1;
    }
    println!(
        "database={path} newly_computed={computed} visited={visited} elapsed={:.3}s",
        started.elapsed().as_secs_f64()
    );
    Ok(summary)
}
fn usage() {
    eprintln!("Usage: syracuse-rs NUMBER [--max-steps N]");
    eprintln!("       syracuse-rs --frontier [--count N] [--workers N] [--max-steps N]");
    eprintln!("       syracuse-rs --start BIGINT --end BIGINT [--workers N] [--max-steps N] (no SQLite for >i64 ranges)");
    eprintln!("       syracuse-rs --start N --end N [--workers N] [--max-steps N] [--database FILE] [--batch-size N]");
}
fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut number = None;
    let mut start: Option<BigUint> = None;
    let mut end: Option<BigUint> = None;
    let mut frontier_mode = false;
    let mut count = 10000u64;
    let mut max_steps = 100_000u64;
    let mut database: Option<String> = None;
    let mut batch_size = 16384u64;
    let mut workers = std::thread::available_parallelism().map_or(1, |n| n.get());
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--frontier" => {
                frontier_mode = true;
                i += 1;
            }
            "--max-steps" | "--start" | "--end" | "--workers" | "--batch-size" | "--database"
            | "--count" => {
                if args[i] == "--database" {
                    if i + 1 >= args.len() {
                        usage();
                        process::exit(2);
                    }
                    database = Some(args[i + 1].clone());
                    i += 2;
                    continue;
                }
                if i + 1 >= args.len() {
                    usage();
                    process::exit(2);
                }
                if args[i] == "--start" || args[i] == "--end" {
                    let value = parse_number(&args[i + 1]);
                    if args[i] == "--start" {
                        start = Some(value);
                    } else {
                        end = Some(value);
                    }
                    i += 2;
                    continue;
                }
                let value = args[i + 1].parse::<u64>().unwrap_or_else(|_| {
                    usage();
                    process::exit(2);
                });
                match args[i].as_str() {
                    "--max-steps" => max_steps = value,
                    "--batch-size" => batch_size = value,
                    "--count" => count = value,
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
    if max_steps == 0
        || workers == 0
        || batch_size == 0
        || count == 0
        || max_steps > i64::MAX as u64
    {
        usage();
        process::exit(2);
    }
    if frontier_mode {
        if number.is_some() || start.is_some() || end.is_some() || database.is_some() {
            eprintln!("--frontier cannot be combined with NUMBER, --start, --end or --database");
            process::exit(2);
        }
        let lo = frontier() + BigUint::one();
        let hi = &lo + (count - 1);
        if let Err(e) = scan_big(&lo, &hi, max_steps, workers) {
            eprintln!("Frontier scan error: {e}");
            process::exit(1);
        }
        return;
    }
    match (number, start, end) {
        (Some(n), None, None) => {
            let r = analyze(&n, max_steps);
            println!(
                "start={n} steps={} peak={} status={}",
                r.steps, r.peak, r.status
            );
        }
        (None, Some(lo), Some(hi)) if !lo.is_zero() && lo <= hi => {
            let t = Instant::now();
            if lo > BigUint::from(u64::MAX) || hi > BigUint::from(u64::MAX) {
                if database.is_some() {
                    eprintln!("SQLite mode only supports start/end <= i64::MAX; use no --database for large integers");
                    process::exit(2);
                }
                if let Err(e) = scan_big(&lo, &hi, max_steps, workers) {
                    eprintln!("Range scan error: {e}");
                    process::exit(1);
                }
                return;
            }
            let lo = lo.to_u64().expect("checked u64");
            let hi = hi.to_u64().expect("checked u64");
            let r = if let Some(ref path) = database {
                match scan_db(lo, hi, max_steps, workers, path, batch_size) {
                    Ok(r) => r,
                    Err(e) => {
                        eprintln!("Database error: {e}");
                        process::exit(1);
                    }
                }
            } else {
                let r = scan(lo, hi, max_steps, workers);
                r
            };
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
    fn fused_odd_step_boundaries() {
        // 3n+1 is always even: exact step limits must not overrun the
        // original recurrence, including when only the odd step fits.
        for n in 1..=2048u64 {
            let start = BigUint::from(n);
            for limit in 1..=12 {
                assert_eq!(
                    analyze(&start, limit),
                    reference(&start, limit),
                    "start={n} max_steps={limit}"
                );
            }
        }
    }
    #[test]
    fn overflow_boundary_parity() {
        for delta in [0u128, 1, 2, 3, 7, 15, 255] {
            let start = BigUint::from(u128::MAX - delta);
            for limit in [1, 2, 3, 4, 10, 100] {
                assert_eq!(analyze(&start, limit), reference(&start, limit));
            }
        }
    }
    #[test]
    fn frontier_value() {
        assert_eq!(frontier().to_string(), "2392312122059207475200");
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