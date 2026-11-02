# Developer: Hamdy Abou El Anein
# Contact: info@daylightlinux.ch
# SPDX-License-Identifier: GPL-3.0-only
import unittest
from syracuse import syracuse

class SyracuseTests(unittest.TestCase):
    def test_known_sequence(self):
        self.assertEqual(syracuse(6), [6, 3, 10, 5, 16, 8, 4, 2, 1])
    def test_one(self):
        self.assertEqual(syracuse(1), [1])
    def test_invalid(self):
        for number in (0, -1, True):
            with self.assertRaises(ValueError):
                syracuse(number)
    def test_step_limit(self):
        with self.assertRaises(RuntimeError):
            syracuse(7, max_steps=2)

if __name__ == "__main__":
    unittest.main()
