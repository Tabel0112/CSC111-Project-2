"""Tests for main-module helpers."""

from __future__ import annotations

import unittest
from argparse import Namespace

from country_input import resolve_country_input
from country_node import CountryNode
from runtime_options import (
    build_initial_shocks,
    choose_visible_country_codes,
    prompt_for_initial_countries,
    prompt_for_initial_shocks,
    prompt_for_runtime_options,
)


class TestMainHelpers(unittest.TestCase):
    """Tests for helper functions used by the entry point."""

    def test_choose_visible_country_codes_keeps_shocked_countries(self) -> None:
        """Countries shocked outside the GDP top-n should still be rendered."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "CHN": CountryNode("CHN", "China", 90.0),
            "ATG": CountryNode("ATG", "Antigua and Barbuda", 1.0),
        }
        wave_history = [
            {"wave": 0, "shock_data": {"USA": 0.2}, "health_data": {}},
            {"wave": 1, "shock_data": {"ATG": 0.1}, "health_data": {}},
        ]

        visible_codes = choose_visible_country_codes(countries, wave_history, top_n=2, metric="gdp")

        self.assertEqual(visible_codes, {"USA", "CHN", "ATG"})

    def test_build_initial_shocks_supports_multiple_countries(self) -> None:
        """Multiple starting countries should accept one shock value per country."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "CHN": CountryNode("CHN", "China", 90.0),
            "DEU": CountryNode("DEU", "Germany", 80.0),
        }

        initial_shocks = build_initial_shocks(
            countries,
            initial_countries="United States; Chnia; Unknownland",
            default_shock=0.2,
            initial_shocks="0.3,0.1",
        )

        self.assertEqual(initial_shocks, {"USA": 0.3, "CHN": 0.1})

    def test_build_initial_shocks_can_apply_one_value_to_all(self) -> None:
        """A single provided shock should broadcast to all valid starting countries."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "CHN": CountryNode("CHN", "China", 90.0),
        }

        initial_shocks = build_initial_shocks(
            countries,
            initial_countries="United States; China",
            default_shock=0.2,
            initial_shocks="0.15",
        )

        self.assertEqual(initial_shocks, {"USA": 0.15, "CHN": 0.15})

    def test_resolve_country_input_supports_autocorrect(self) -> None:
        """Country names should resolve with a closest-match suggestion when misspelled."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "DEU": CountryNode("DEU", "Germany", 80.0),
        }

        resolved_code, suggestion = resolve_country_input("Germnay", countries)

        self.assertEqual(resolved_code, "DEU")
        self.assertEqual(suggestion, "Germany")

    def test_resolve_country_input_ignores_distant_names(self) -> None:
        """Unrelated text should not be autocorrected into a real country."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "DEU": CountryNode("DEU", "Germany", 80.0),
        }

        resolved_code, suggestion = resolve_country_input("Unknownland", countries)

        self.assertIsNone(resolved_code)
        self.assertIsNone(suggestion)

    def test_prompt_for_runtime_options_accepts_defaults(self) -> None:
        """Blank terminal input should preserve existing defaults."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "CHN": CountryNode("CHN", "China", 90.0),
            "DEU": CountryNode("DEU", "Germany", 80.0),
        }
        args = Namespace(
            initial_countries="",
            initial_shock=0.2,
            initial_shocks="",
            threshold=0.002,
            top_n=170,
            top_k=40,
            visible_by="trade",
            hide_edges=False,
        )
        answers = iter(["", "", "", "", "", "", "", "", "", "", "", ""])

        prompted = prompt_for_runtime_options(
            args,
            countries,
            input_func=lambda _prompt: next(answers),
            show_intro=False,
        )

        self.assertEqual(prompted.initial_countries, "United States; China; Germany; Japan; India")
        self.assertEqual(prompted.initial_shocks, "0.35,0.3,0.25,0.2,0.18")
        self.assertEqual(prompted.threshold, 0.002)
        self.assertEqual(prompted.top_n, 170)
        self.assertEqual(prompted.top_k, 40)
        self.assertEqual(prompted.visible_by, "trade")
        self.assertFalse(prompted.hide_edges)

    def test_prompt_for_runtime_options_overrides_values(self) -> None:
        """Prompt responses should replace the defaults when provided."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "CHN": CountryNode("CHN", "China", 90.0),
            "DEU": CountryNode("DEU", "Germany", 80.0),
        }
        args = Namespace(
            initial_countries="",
            initial_shock=0.2,
            initial_shocks="",
            threshold=0.003,
            top_n=120,
            top_k=20,
            visible_by="gdp",
            hide_edges=False,
        )
        answers = iter(["0.01", "80", "12", "trade", "y", "United States", "done", "0.25"])

        prompted = prompt_for_runtime_options(
            args,
            countries,
            input_func=lambda _prompt: next(answers),
            show_intro=False,
        )

        self.assertEqual(prompted.initial_countries, "United States")
        self.assertEqual(prompted.initial_shocks, "0.25")
        self.assertEqual(prompted.threshold, 0.01)
        self.assertEqual(prompted.top_n, 80)
        self.assertEqual(prompted.top_k, 12)
        self.assertEqual(prompted.visible_by, "trade")
        self.assertTrue(prompted.hide_edges)

    def test_prompt_for_initial_countries_uses_done_and_autocorrect(self) -> None:
        """Country entry should collect one country at a time until done is entered."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "CHN": CountryNode("CHN", "China", 90.0),
            "DEU": CountryNode("DEU", "Germany", 80.0),
        }
        args = Namespace(
            initial_countries="United States; China; Germany",
        )
        answers = iter(["Germnay", "y", "Chnia", "y", "done"])

        selected = prompt_for_initial_countries(
            args,
            countries,
            input_func=lambda _prompt: next(answers),
            show_intro=False,
        )

        self.assertEqual(selected, "Germany; China")

    def test_prompt_for_initial_countries_rejects_suggestion_when_declined(self) -> None:
        """Declining an autocorrect suggestion should force a re-entry."""
        countries = {
            "USA": CountryNode("USA", "United States", 100.0),
            "DEU": CountryNode("DEU", "Germany", 80.0),
        }
        args = Namespace(
            initial_countries="United States; Germany",
        )
        answers = iter(["Germnay", "n", "Germany", "done"])

        selected = prompt_for_initial_countries(
            args,
            countries,
            input_func=lambda _prompt: next(answers),
            show_intro=False,
        )

        self.assertEqual(selected, "Germany")

    def test_prompt_for_initial_shocks_prompts_per_country(self) -> None:
        """Each selected country should receive its own shock prompt."""
        args = Namespace(
            initial_countries="United States; Germany",
            initial_shock=0.2,
            initial_shocks="",
        )
        answers = iter(["0.4", ""])

        entered_shocks = prompt_for_initial_shocks(
            args,
            input_func=lambda _prompt: next(answers),
        )

        self.assertEqual(entered_shocks, "0.4,0.25")


if __name__ == "__main__":
    unittest.main()
