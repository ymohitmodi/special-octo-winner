"""Unit tests for the deterministic parts of the nyx showcase engine (offline)."""
import sys
import unittest
from pathlib import Path

# The promoter uses flat module imports (`import nyx_engine`), so expose src/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import nyx_engine  # noqa: E402


class StableIndexTests(unittest.TestCase):
    def test_same_run_id_always_maps_to_same_slot(self):
        first = nyx_engine._stable_index("2026-07-04-thu", 3)
        for _ in range(5):
            self.assertEqual(first, nyx_engine._stable_index("2026-07-04-thu", 3))

    def test_index_is_always_in_range(self):
        for n in (1, 2, 3, 7):
            for run_id in ("a", "b", "2026-01-01", "x" * 50):
                self.assertTrue(0 <= nyx_engine._stable_index(run_id, n) < n)

    def test_rotation_visits_more_than_one_slot(self):
        slots = {nyx_engine._stable_index(f"run-{i}", 3) for i in range(30)}
        self.assertGreater(len(slots), 1)


if __name__ == "__main__":
    unittest.main()
