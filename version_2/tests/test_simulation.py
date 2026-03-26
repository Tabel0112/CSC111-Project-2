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
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            substitution_concentration_penalty=0.0,
            inventory_stress_penalty=0.0,
        )

        self.assertAlmostEqual(history[1]["shock_data"]["CAN"], 0.2)

    def test_importer_disruption_can_push_back_on_exporter(self) -> None:
        """A disrupted importer should create reverse demand pressure on its exporter."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        usa.add_trading_partner(can, 0.0, 0.4)
        countries = {"USA": usa, "CAN": can}

        history = run_time_step_simulation(
            countries,
            {"CAN": 0.5},
            threshold=0.01,
            max_steps=3,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            trade_pressure_scale=1.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            substitution_concentration_penalty=0.0,
            inventory_stress_penalty=0.0,
        )

        self.assertAlmostEqual(history[1]["shock_data"]["USA"], 0.14)

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
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            substitution_concentration_penalty=0.0,
            inventory_stress_penalty=0.0,
        )

        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]["inventory_data"]["CAN"], 0.05)

    def test_health_stays_flat_when_no_new_damage_occurs(self) -> None:
        """Health should stay at the post-shock level once pressure stops."""
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
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            substitution_concentration_penalty=0.0,
            inventory_stress_penalty=0.0,
        )

        self.assertAlmostEqual(history[0]["health_data"]["USA"], 0.6)
        self.assertAlmostEqual(history[-1]["health_data"]["USA"], history[0]["health_data"]["USA"])

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
            inventory_rebuild_rate=0.0,
            health_damage_scale=0.75,
            shortage_damage_scale=0.0,
            persistence=0.3,
            delay_share=0.0,
        )
        high_history = run_time_step_simulation(
            high_countries,
            {"USA": 0.8},
            threshold=0.01,
            max_steps=8,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            trade_pressure_scale=0.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=0.75,
            shortage_damage_scale=0.0,
            persistence=0.3,
            delay_share=0.0,
        )

        self.assertGreater(
            low_history[-1]["health_data"]["USA"],
            high_history[-1]["health_data"]["USA"],
        )

    def test_simulation_stops_when_disruption_fades(self) -> None:
        """The simulation should end early once disruption and deferred pressure both stop."""
        countries = {"USA": CountryNode("USA", "United States", 100.0)}

        history = run_time_step_simulation(
            countries,
            {"USA": 0.2},
            threshold=0.5,
            max_steps=5,
            inventory_buffer=0.0,
            substitution_rate=0.0,
            trade_pressure_scale=0.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            substitution_concentration_penalty=0.0,
            inventory_stress_penalty=0.0,
        )

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["shock_data"], {"USA": 0.2})

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
            inventory_rebuild_rate=0.0,
            health_damage_scale=1.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            substitution_pressure_exponent=1.0,
            substitution_concentration_penalty=0.0,
            inventory_stress_penalty=0.0,
        )

        self.assertAlmostEqual(history[0]["shortage_data"]["CAN"], 0.1)
        self.assertAlmostEqual(history[0]["deferred_shortage_data"]["CAN"], 0.1)
        self.assertAlmostEqual(history[1]["pressure_data"]["CAN"], 0.1)
        self.assertAlmostEqual(history[1]["shock_data"]["CAN"], 0.1)

    def test_concentrated_pressure_reduces_substitution_more_than_diversified_pressure(self) -> None:
        """Pressure from one dominant source should be harder to substitute away."""
        usa = CountryNode("USA", "United States", 100.0)
        jpn = CountryNode("JPN", "Japan", 100.0)
        kor = CountryNode("KOR", "South Korea", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)

        usa.add_trading_partner(can, 0.2)
        jpn.add_trading_partner(can, 0.1)
        kor.add_trading_partner(can, 0.1)

        concentrated_history = run_time_step_simulation(
            {"USA": usa, "CAN": can},
            {"USA": 0.4},
            threshold=0.0,
            max_steps=1,
            inventory_buffer=0.0,
            substitution_rate=0.5,
            trade_pressure_scale=1.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=0.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            substitution_concentration_penalty=0.5,
            inventory_stress_penalty=0.0,
        )
        diversified_history = run_time_step_simulation(
            {"USA": usa, "JPN": jpn, "KOR": kor, "CAN": can},
            {"USA": 0.1333333333, "JPN": 0.2666666667, "KOR": 0.2666666667},
            threshold=0.0,
            max_steps=1,
            inventory_buffer=0.0,
            substitution_rate=0.5,
            trade_pressure_scale=1.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=0.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            substitution_pressure_exponent=1.0,
            substitution_concentration_penalty=0.5,
            inventory_stress_penalty=0.0,
        )

        self.assertGreater(
            concentrated_history[0]["shortage_data"]["CAN"],
            diversified_history[0]["shortage_data"]["CAN"],
        )

    def test_large_shocks_limit_usable_inventory(self) -> None:
        """Very large shocks should make a smaller share of inventory usable in one step."""
        usa = CountryNode("USA", "United States", 100.0)
        can = CountryNode("CAN", "Canada", 50.0)
        usa.add_trading_partner(can, 0.5)
        countries = {"USA": usa, "CAN": can}

        low_pressure_history = run_time_step_simulation(
            countries,
            {"USA": 0.2},
            threshold=0.0,
            max_steps=1,
            inventory_buffer=0.25,
            substitution_rate=0.0,
            trade_pressure_scale=1.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=0.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            inventory_stress_penalty=0.75,
            inventory_stress_exponent=1.0,
        )
        usa_high = CountryNode("USA", "United States", 100.0)
        can_high = CountryNode("CAN", "Canada", 50.0)
        usa_high.add_trading_partner(can_high, 0.5)
        high_pressure_history = run_time_step_simulation(
            {"USA": usa_high, "CAN": can_high},
            {"USA": 0.8},
            threshold=0.0,
            max_steps=1,
            inventory_buffer=0.25,
            substitution_rate=0.0,
            trade_pressure_scale=1.0,
            inventory_rebuild_rate=0.0,
            health_damage_scale=0.0,
            shortage_damage_scale=0.0,
            persistence=0.0,
            delay_share=0.0,
            inventory_stress_penalty=0.75,
            inventory_stress_exponent=1.0,
        )

        self.assertGreater(
            low_pressure_history[0]["inventory_data"]["CAN"],
            high_pressure_history[0]["inventory_data"]["CAN"],
        )
        self.assertGreater(
            high_pressure_history[0]["shortage_data"].get("CAN", 0.0),
            low_pressure_history[0]["shortage_data"].get("CAN", 0.0),
        )


if __name__ == "__main__":
    unittest.main()
