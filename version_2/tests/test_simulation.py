"""Tests for the time-step simulation."""

from __future__ import annotations

import unittest

from country_node import CountryNode
from simulation import run_time_step_simulation


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
    """Tests for the time-step simulation."""

    def test_step_history_structure(self) -> None:
        """The simulation should save step, impact, health, and inventory data."""
        countries = build_small_graph()
        history = run_time_step_simulation(countries, {"USA": 0.2}, threshold=0.01, max_steps=4)

        self.assertGreaterEqual(len(history), 1)
        self.assertIn("step", history[0])
        self.assertIn("shock_data", history[0])
        self.assertIn("health_data", history[0])
        self.assertIn("inventory_data", history[0])
        self.assertIn("pressure_data", history[0])

    def test_trade_pressure_moves_to_importer_next_step(self) -> None:
        """Exporter disruption should create an importer disruption on the next step."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        usa.add_trading_partner(can, 0.5)
        countries = {"USA": usa, "CAN": can}

        history = run_time_step_simulation(
            countries,
            {"USA": 0.4},
            threshold=0.01,
            max_steps=3,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            trade_pressure_scale=1.0,
            recovery_rate=0.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            health_gap_pass_through=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            recovery_pressure_sensitivity=0.0,
        )

        self.assertAlmostEqual(history[1]["shock_data"]["CAN"], 0.2)

    def test_inventory_can_absorb_first_round_shortage(self) -> None:
        """Inventory should be able to stop a small shortage from propagating."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        usa.add_trading_partner(can, 0.5)
        countries = {"USA": usa, "CAN": can}

        history = run_time_step_simulation(
            countries,
            {"USA": 0.4},
            threshold=0.01,
            max_steps=3,
            inventory_buffer=0.25,
            substitution_rate=0.0,
            trade_pressure_scale=1.0,
            recovery_rate=0.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            health_gap_pass_through=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            recovery_pressure_sensitivity=0.0,
        )

        self.assertEqual(len(history), 3)
        self.assertAlmostEqual(history[0]["inventory_data"]["CAN"], 0.05)
        self.assertEqual(history[1]["shock_data"], {})
        self.assertEqual(history[2]["shock_data"], {})

    def test_recovery_restores_health_over_time(self) -> None:
        """Health should recover over time when persistence is disabled."""
        usa = CountryNode("USA", "United States", 100.0)
        countries = {"USA": usa}

        history = run_time_step_simulation(
            countries,
            {"USA": 0.4},
            threshold=0.5,
            max_steps=3,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            trade_pressure_scale=0.0,
            recovery_rate=0.2,
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            health_gap_pass_through=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            recovery_pressure_sensitivity=0.0,
        )

        self.assertAlmostEqual(history[0]["health_data"]["USA"], 0.648)
        self.assertGreater(history[-1]["health_data"]["USA"], history[0]["health_data"]["USA"])

    def test_health_stays_valid(self) -> None:
        """Health values should stay within [0.0, 1.0]."""
        countries = build_small_graph()
        history = run_time_step_simulation(countries, {"USA": 0.9}, threshold=0.01, max_steps=6)

        for step in history:
            for value in step["health_data"].values():
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_different_initial_shocks_do_not_force_same_final_health(self) -> None:
        """Different starting shocks should lead to different final health outcomes."""
        low_countries = {"USA": CountryNode("USA", "United States", 100.0)}
        high_countries = {"USA": CountryNode("USA", "United States", 100.0)}

        low_history = run_time_step_simulation(
            low_countries,
            {"USA": 0.1},
            threshold=0.01,
            max_steps=8,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            trade_pressure_scale=0.0,
            recovery_rate=0.08,
            inventory_rebuild_rate=0.0,
            health_damage_scale=0.75,
            shortage_damage_scale=0.0,
            persistence=0.3,
            health_gap_pass_through=0.0,
            delay_share=0.0,
            recovery_pressure_sensitivity=0.0,
        )
        high_history = run_time_step_simulation(
            high_countries,
            {"USA": 0.8},
            threshold=0.01,
            max_steps=8,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            trade_pressure_scale=0.0,
            recovery_rate=0.08,
            inventory_rebuild_rate=0.0,
            health_damage_scale=0.75,
            shortage_damage_scale=0.0,
            persistence=0.3,
            health_gap_pass_through=0.0,
            delay_share=0.0,
            recovery_pressure_sensitivity=0.0,
        )

        self.assertGreater(
            low_history[-1]["health_data"]["USA"],
            high_history[-1]["health_data"]["USA"],
        )

    def test_simulation_runs_full_requested_step_count(self) -> None:
        """The simulation should continue through max_steps so later recovery is visible."""
        countries = {"USA": CountryNode("USA", "United States", 100.0)}

        history = run_time_step_simulation(
            countries,
            {"USA": 0.2},
            threshold=0.5,
            max_steps=5,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            trade_pressure_scale=0.0,
            recovery_rate=0.1,
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            health_gap_pass_through=0.0,
            delay_share=0.0,
            recovery_pressure_sensitivity=0.0,
        )

        self.assertEqual(len(history), 5)
        self.assertEqual(history[1]["shock_data"], {})

    def test_delay_share_pushes_shortage_into_later_step(self) -> None:
        """A delay share should split shortages across immediate and deferred channels."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        usa.add_trading_partner(can, 0.5)
        countries = {"USA": usa, "CAN": can}

        history = run_time_step_simulation(
            countries,
            {"USA": 0.4},
            threshold=0.01,
            max_steps=3,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            delay_share=0.5,
            trade_pressure_scale=1.0,
            recovery_rate=0.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            health_gap_pass_through=0.0,
            substitution_pressure_exponent=1.0,
            recovery_pressure_sensitivity=0.0,
        )

        self.assertAlmostEqual(history[0]["shortage_data"]["CAN"], 0.1)
        self.assertAlmostEqual(history[0]["deferred_shortage_data"]["CAN"], 0.1)
        self.assertAlmostEqual(history[1]["pressure_data"]["CAN"], 0.1)
        self.assertAlmostEqual(history[1]["shock_data"]["CAN"], 0.1)


if __name__ == "__main__":
    unittest.main()
