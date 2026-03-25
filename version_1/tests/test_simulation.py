"""Tests for BFS wave simulation."""

from __future__ import annotations

import unittest

from country_node import CountryNode
from simulation import run_bfs_simulation


def build_small_graph() -> dict[str, CountryNode]:
    """Return a small graph for simulation tests."""
    usa = CountryNode("USA", "United States", 100.0)
    can = CountryNode("CAN", "Canada", 50.0)
    mex = CountryNode("MEX", "Mexico", 40.0)

    usa.add_trading_partner(can, 0.5)
    usa.add_trading_partner(mex, 0.2)
    can.add_trading_partner(mex, 0.1)

    return {"USA": usa, "CAN": can, "MEX": mex}


class TestSimulation(unittest.TestCase):
    """Tests for the BFS wave simulation."""

    def test_wave_history_structure(self) -> None:
        """The simulation should save wave, shock, and health data."""
        countries = build_small_graph()
        history = run_bfs_simulation(countries, {"USA": 0.2}, threshold=0.01, max_waves=4)

        self.assertGreaterEqual(len(history), 1)
        self.assertIn("wave", history[0])
        self.assertIn("shock_data", history[0])
        self.assertIn("health_data", history[0])

    def test_same_wave_shocks_are_combined(self) -> None:
        """Two shocks reaching the same country in one wave should add together."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        mex = CountryNode("MEX", "Mexico", 40.0)

        usa.add_trading_partner(mex, 0.2)
        can.add_trading_partner(mex, 0.3)
        countries = {"USA": usa, "CAN": can, "MEX": mex}

        history = run_bfs_simulation(
            countries,
            {"USA": 0.5, "CAN": 0.5},
            threshold=0.01,
            max_waves=3,
        )

        self.assertAlmostEqual(history[1]["shock_data"]["MEX"], 0.25)

    def test_threshold_stops_tiny_waves(self) -> None:
        """Waves below the threshold should not continue."""
        countries = build_small_graph()
        history = run_bfs_simulation(countries, {"USA": 0.05}, threshold=0.1, max_waves=5)

        self.assertEqual(len(history), 1)

    def test_persistence_can_extend_cascade(self) -> None:
        """Residual aftershocks should allow a longer replay when enabled."""
        countries = build_small_graph()
        history = run_bfs_simulation(
            countries,
            {"USA": 0.2},
            threshold=0.01,
            max_waves=5,
            persistence=0.2,
        )

        self.assertGreaterEqual(len(history), 3)

    def test_health_stays_valid(self) -> None:
        """Health values should stay within [0.0, 1.0]."""
        countries = build_small_graph()
        history = run_bfs_simulation(countries, {"USA": 0.9}, threshold=0.01, max_waves=5)

        for wave in history:
            for value in wave["health_data"].values():
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
