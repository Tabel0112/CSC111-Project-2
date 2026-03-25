"""Wave-by-wave shock simulation."""

from __future__ import annotations

from typing import Any

from config import (
    DEFAULT_MAX_WAVES,
    DEFAULT_THRESHOLD,
    MIN_HEALTH_CUTOFF,
    SHOCK_PERSISTENCE,
)
from country_node import CountryNode
from utils import clamp_shock, country_dict_to_snapshot


def combine_wave_shocks(
    countries: dict[str, CountryNode],
    current_wave: dict[str, float],
    threshold: float,
    persistence: float,
) -> dict[str, float]:
    """Combine direct propagation with a smaller residual aftershock."""
    next_wave_totals = {}
    for exporter_code, outgoing_shock in current_wave.items():
        exporter = countries[exporter_code]

        for importer, weight in exporter.trading_partners.items():
            propagated_shock = clamp_shock(outgoing_shock * weight)
            if propagated_shock <= 0:
                continue

            if importer.code not in next_wave_totals:
                next_wave_totals[importer.code] = 0.0
            next_wave_totals[importer.code] += propagated_shock

        residual_shock = clamp_shock(outgoing_shock * persistence)
        if residual_shock > 0:
            if exporter_code not in next_wave_totals:
                next_wave_totals[exporter_code] = 0.0
            next_wave_totals[exporter_code] = max(next_wave_totals[exporter_code], residual_shock)

    combined = {}
    for code, total_shock in next_wave_totals.items():
        bounded_total = clamp_shock(total_shock)
        if bounded_total >= threshold and countries[code].current_health > MIN_HEALTH_CUTOFF:
            combined[code] = bounded_total

    return combined


def run_bfs_simulation(
    countries: dict[str, CountryNode],
    initial_shocks: dict[str, float],
    threshold: float = DEFAULT_THRESHOLD,
    max_waves: int = DEFAULT_MAX_WAVES,
    persistence: float = SHOCK_PERSISTENCE,
) -> list[dict[str, Any]]:
    """Run the wave simulation and return replay-friendly history.

    The simulator is intentionally structured around explicit current-wave and
    next-wave dictionaries so that future work can inject extra shocks mid-run.
    """
    wave_history = []
    current_wave = {
        code: clamp_shock(shock)
        for code, shock in initial_shocks.items()
        if code in countries and clamp_shock(shock) > 0
    }
    wave_number = 0

    while current_wave and wave_number < max_waves:
        for code, shock in current_wave.items():
            countries[code].apply_shock(shock)

        wave_history.append(
            {
                "wave": wave_number,
                "shock_data": dict(sorted(current_wave.items())),
                "health_data": country_dict_to_snapshot(countries),
            }
        )

        current_wave = combine_wave_shocks(countries, current_wave, threshold, persistence)
        wave_number += 1

    return wave_history
