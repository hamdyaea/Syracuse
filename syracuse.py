#!/usr/bin/env python3
# Developer: Hamdy Abou El Anein
# Contact: info@daylightlinux.ch
# SPDX-License-Identifier: GPL-3.0-only
"""Iterative Collatz/Syracuse sequence calculator."""
from __future__ import annotations
import argparse

def syracuse(number: int, max_steps: int = 100000) -> list[int]:
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("Starting number must be a positive integer")
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    sequence = [number]
    for _ in range(max_steps):
        if number == 1:
            return sequence
        number = number // 2 if number % 2 == 0 else 3 * number + 1
        sequence.append(number)
    if number == 1:
        return sequence
    raise RuntimeError("Maximum steps reached before 1")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number", nargs="?", type=int, help="Positive starting number")
    parser.add_argument("--max-steps", type=int, default=100000)
    args = parser.parse_args()
    number = args.number if args.number is not None else int(input("Enter a number: "))
    try:
        print(*syracuse(number, args.max_steps), sep="\n")
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))

if __name__ == "__main__":
    main()
