"""Tests for the CountryNode class."""

from __future__ import annotations

import unittest

from country_node import CountryNode


class TestCountryNode(unittest.TestCase):
    """Tests for CountryNode."""

    def test_add_trading_partner(self) -> None:
        """Adding a partner should store the edge weight."""
        usa = CountryNode("USA", "United States", 10.0)
        can = CountryNode("CAN", "Canada", 5.0)
        usa.add_trading_partner(can, 0.25, 0.1)

        self.assertIn(can, usa.trading_partners)
        self.assertAlmostEqual(usa.trading_partners[can]["supply_weight"], 0.25)
        self.assertAlmostEqual(usa.trading_partners[can]["demand_weight"], 0.1)

    def test_apply_shock(self) -> None:
        """Applying a shock should reduce health multiplicatively."""
        usa = CountryNode("USA", "United States", 10.0)
        usa.apply_shock(0.2)
        usa.apply_shock(0.5)

        self.assertAlmostEqual(usa.current_health, 0.4)

    def test_reset_health(self) -> None:
        """Resetting should restore health to 1.0."""
        usa = CountryNode("USA", "United States", 10.0)
        usa.apply_shock(0.7)
        usa.reset_health()

        self.assertEqual(usa.current_health, 1.0)

if __name__ == "__main__":
    unittest.main()
