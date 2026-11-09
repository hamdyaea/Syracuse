import sqlite3
import tempfile
import unittest
from pathlib import Path

from explore import explore, records, sample_numbers
from syracuse import analyze


class ExplorationTests(unittest.TestCase):
    def test_sample_reproducibility_and_bit_length(self):
        a = list(sample_numbers(20, 80, 42))
        self.assertEqual(a, list(sample_numbers(20, 80, 42)))
        self.assertTrue(all(n.bit_length() == 80 for n in a))

    def test_explore_parallel_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "explore.db"
            explore(50, 24, 42, 1000, 2, db, 10)
            with sqlite3.connect(db) as conn:
                first = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
                rows = conn.execute("SELECT start,steps,peak,status FROM samples").fetchall()
            self.assertEqual(first, len(set(sample_numbers(50, 24, 42))))
            for n, steps, peak, status in rows:
                self.assertEqual((int(n), steps, int(peak), status),
                                 analyze(int(n), 1000))
            explore(50, 24, 42, 1000, 2, db, 10)
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM samples").fetchone()[0], first)
            longest, highest = records(db)
            self.assertGreater(longest[0], 0)
            self.assertGreater(highest[0], 0)


if __name__ == "__main__":
    unittest.main()
