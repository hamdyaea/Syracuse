# Syracuse / Collatz Sequence

**Developer:** Hamdy Abou El Anein  
**Contact:** info@daylightlinux.ch  
**License:** See LICENSE.

A Python 3 command-line implementation of the Syracuse (Collatz) sequence. The algorithm is iterative and uses exact integer arithmetic. A configurable maximum number of steps prevents unbounded execution; termination for every positive integer is not mathematically proven.

```sh
python3 syracuse.py 27
python3 syracuse.py 27 --max-steps 1000
python3 -m unittest discover -s tests -v
```

Original code: [old branch](https://github.com/hamdyaea/Syracuse/tree/old).
