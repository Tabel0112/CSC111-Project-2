"""Runtime option parsing and interactive prompt helpers."""

from __future__ import annotations

import argparse

from config import DEFAULT_INITIAL_COUNTRIES, DEFAULT_INITIAL_SHOCKS
from country_input import resolve_country_input
from country_node import CountryNode
from graph_builder import get_visible_country_codes, get_visible_country_codes_by_metric


def parse_csv_values(raw_value: str) -> list[str]:
    """Return non-empty comma-separated values."""
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def parse_country_names(raw_value: str) -> list[str]:
    """Return country names split by semicolons when present, otherwise commas."""
    separator = ";" if ";" in raw_value else ","
    return [item.strip() for item in raw_value.split(separator) if item.strip()]


def build_initial_shocks(
    countries: dict[str, CountryNode],
    initial_countries: str,
    default_shock: float,
    initial_shocks: str,
) -> dict[str, float]:
    """Return the wave-0 shock mapping from selected country names and shock values."""
    selected_codes = _resolve_selected_country_codes(
        countries,
        parse_country_names(initial_countries or DEFAULT_INITIAL_COUNTRIES),
    )
    if not selected_codes:
        raise ValueError("No valid starting countries were selected.")

    raw_shocks = parse_csv_values(initial_shocks)
    if not raw_shocks:
        return {code: default_shock for code in selected_codes}

    try:
        shock_values = [float(value) for value in raw_shocks]
    except ValueError as exc:
        raise ValueError("--initial-shocks must be numeric.") from exc

    if len(shock_values) == 1:
        return {code: shock_values[0] for code in selected_codes}

    if len(shock_values) != len(selected_codes):
        raise ValueError(
            "--initial-shocks must contain either one value or the same number of values "
            "as valid --initial-countries."
        )

    return dict(zip(selected_codes, shock_values))


def choose_visible_country_codes(
    countries: dict[str, CountryNode],
    wave_history: list[dict[str, object]],
    top_n: int,
    metric: str,
) -> set[str]:
    """Return visible countries, always keeping any country shocked during the replay."""
    visible_codes = (
        get_visible_country_codes(countries, top_n)
        if metric == "gdp"
        else get_visible_country_codes_by_metric(countries, top_n, metric)
    )
    shocked_codes = {
        code
        for wave_snapshot in wave_history
        for code in wave_snapshot["shock_data"]
        if code in countries
    }
    return visible_codes | shocked_codes


def prompt_for_runtime_options(
    args: argparse.Namespace,
    countries: dict[str, CountryNode],
    input_func: object = input,
    show_intro: bool = True,
) -> argparse.Namespace:
    """Prompt for runtime settings in an interactive terminal session."""
    if show_intro:
        print("Press Enter to keep the default shown in brackets.")

    args.threshold = _prompt_float("Shock threshold", args.threshold, input_func)
    args.top_n = _prompt_int("Visible country count", args.top_n, input_func)
    args.top_k = _prompt_int("Top outgoing partners per country", args.top_k, input_func)
    args.visible_by = _prompt_choice(
        "Visible-country ranking",
        args.visible_by,
        ["gdp", "exports", "imports", "trade"],
        input_func,
    )
    args.hide_edges = _prompt_bool("Hide edges", args.hide_edges, input_func)
    args.initial_countries = prompt_for_initial_countries(
        args,
        countries,
        input_func,
        show_intro=show_intro,
    )
    args.initial_shocks = prompt_for_initial_shocks(args, input_func)
    return args


def prompt_for_initial_countries(
    args: argparse.Namespace,
    countries: dict[str, CountryNode],
    input_func: object = input,
    show_intro: bool = True,
) -> str:
    """Prompt for starting countries one at a time until the user types done."""
    default_countries = args.initial_countries or DEFAULT_INITIAL_COUNTRIES
    if show_intro:
        print("Enter one starting country at a time.")
        print(
            "Type 'done' when finished, or press Enter immediately to use the default: "
            f"{default_countries}"
        )

    chosen_names = []
    chosen_codes = set()
    index = 1

    while True:
        response = input_func(f"Starting country {index}: ").strip()
        if response == "":
            if not chosen_names:
                return default_countries
            print("Type 'done' when you finish entering countries.")
            continue

        if response.lower() in {"done", "finish", "confirm"}:
            if chosen_names:
                return "; ".join(chosen_names)
            return default_countries

        resolved_code, suggestion = resolve_country_input(response, countries)
        if resolved_code is None:
            print("Country not recognized. Try the full country name, or a close spelling.")
            continue

        resolved_name = _country_name(countries, resolved_code)
        if suggestion is not None:
            use_suggestion = _prompt_bool(
                f'Did you mean "{resolved_name}"?',
                True,
                input_func,
            )
            if not use_suggestion:
                print("Okay, try entering the country again.")
                continue

        if resolved_code in chosen_codes:
            print(f"{resolved_name} is already in the list.")
            continue

        chosen_codes.add(resolved_code)
        chosen_names.append(resolved_name)
        index += 1


def prompt_for_initial_shocks(
    args: argparse.Namespace,
    input_func: object = input,
) -> str:
    """Prompt for one initial shock per selected country, with per-country defaults."""
    selected_countries = parse_country_names(args.initial_countries)
    default_lookup = _default_shock_lookup()
    if not selected_countries:
        return args.initial_shocks or DEFAULT_INITIAL_SHOCKS or str(args.initial_shock)

    entered_shocks = []
    for country_name in selected_countries:
        default_value = default_lookup.get(country_name, args.initial_shock)
        shock_value = _prompt_float(f"Initial shock for {country_name}", default_value, input_func)
        entered_shocks.append(str(shock_value))

    return ",".join(entered_shocks)


def _resolve_selected_country_codes(
    countries: dict[str, CountryNode],
    requested_names: list[str],
) -> list[str]:
    """Return unique ISO-3 codes for the requested country names."""
    selected_codes = []
    seen_codes = set()

    for country_input in requested_names:
        resolved_code, suggestion = resolve_country_input(country_input, countries)
        if resolved_code is None or resolved_code in seen_codes:
            continue

        if suggestion is not None:
            print(f'Using closest country match for "{country_input}": {suggestion}')

        selected_codes.append(resolved_code)
        seen_codes.add(resolved_code)

    return selected_codes


def _country_name(countries: dict[str, CountryNode], code: str) -> str:
    """Return the display name for a country code."""
    return str(getattr(countries[code], "name", code))


def _default_shock_lookup() -> dict[str, float]:
    """Return the configured default shock for each default starting country."""
    default_names = parse_country_names(DEFAULT_INITIAL_COUNTRIES)
    default_values = parse_csv_values(DEFAULT_INITIAL_SHOCKS)
    try:
        shocks = [float(value) for value in default_values]
    except ValueError:
        return {}

    if not shocks:
        return {}

    if len(shocks) == 1:
        return {name: shocks[0] for name in default_names}

    return {name: shock for name, shock in zip(default_names, shocks)}


def _prompt_with_default(
    label: str,
    default: str,
    input_func: object = input,
) -> str:
    """Return terminal input, or the supplied default when left blank."""
    response = input_func(f"{label} [{default}]: ").strip()
    return response or default


def _prompt_choice(
    label: str,
    default: str,
    choices: list[str],
    input_func: object = input,
) -> str:
    """Prompt until the response matches one of the allowed choices."""
    while True:
        response = _prompt_with_default(
            f"{label} ({'/'.join(choices)})",
            default,
            input_func,
        ).lower()
        if response in choices:
            return response
        print(f"Please choose one of: {', '.join(choices)}")


def _prompt_float(
    label: str,
    default: float,
    input_func: object = input,
) -> float:
    """Prompt for a float, allowing Enter to keep the default."""
    while True:
        response = _prompt_with_default(label, str(default), input_func)
        try:
            return float(response)
        except ValueError:
            print("Please enter a number.")


def _prompt_int(
    label: str,
    default: int,
    input_func: object = input,
) -> int:
    """Prompt for an integer, allowing Enter to keep the default."""
    while True:
        response = _prompt_with_default(label, str(default), input_func)
        try:
            return int(response)
        except ValueError:
            print("Please enter an integer.")


def _prompt_bool(
    label: str,
    default: bool,
    input_func: object = input,
) -> bool:
    """Prompt for yes/no, allowing Enter to keep the default."""
    default_text = "y" if default else "n"
    while True:
        response = _prompt_with_default(f"{label} (y/n)", default_text, input_func).lower()
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Please enter y or n.")
