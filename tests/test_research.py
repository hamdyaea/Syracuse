import sqlite3
import tempfile
import unittest
from pathlib import Path

from syracuse import analyze, export_csv, scan, syracuse


class SyracuseTests(unittest.TestCase):
    def test_known_sequence(self):
        self.assertEqual(syracuse(6), [6, 3, 10, 5, 16, 8, 4, 2, 1])

    def test_27(self):
        self.assertEqual(analyze(27)[:3], (27, 111, 9232))

    def test_limits(self):
        self.assertEqual(analyze(27, 1)[3], "limit")
        self.assertEqual(syracuse(1), [1])
        with self.assertRaises(ValueError):
            syracuse(0)

    def test_resume_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "results.db"
            csv = Path(directory) / "results.csv"
            scan(1, 30, 100, 1, db, 5)
            scan(1, 30, 100, 1, db, 5)
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute(
                    "SELECT COUNT(*) FROM results"
                ).fetchone()[0], 30)
            export_csv(db, csv)
            self.assertEqual(len(csv.read_text().splitlines()), 31)

    def test_parallel_scan_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "parallel.db"
            scan(1, 150, 1000, 2, db, 10)
            scan(1, 150, 1000, 2, db, 10)
            with sqlite3.connect(db) as connection:
                count, incomplete = connection.execute(
                    "SELECT COUNT(*), SUM(status != 'reached_1') FROM results"
                ).fetchone()
                self.assertEqual(count, 150)
                self.assertEqual(incomplete, 0)

    def test_retry_after_increased_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "results.db"
            scan(27, 27, 1, 1, db)
            scan(27, 27, 200, 1, db)
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute(
                    "SELECT status FROM results WHERE start=27"
                ).fetchone()[0], "reached_1")


if __name__ == "__main__":
    unittest.main()
