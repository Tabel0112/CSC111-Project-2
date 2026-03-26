"""Time-step trade disruption simulation with buffering and persistence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from config import (
    DEFAULT_INVENTORY_BUFFER,
    DEFAULT_THRESHOLD,
    DEFAULT_TIME_STEPS,
    DISRUPTION_PERSISTENCE,
    HEALTH_DAMAGE_SCALE,
    INVENTORY_REBUILD_RATE,
    MIN_HEALTH_CUTOFF,
    SHORTAGE_DAMAGE_SCALE,
    SHORTAGE_DELAY_SHARE,
    SUBSTITUTION_RATE,
    SUBSTITUTION_PRESSURE_EXPONENT,
    TRADE_PRESSURE_SCALE,
)
from country_node import CountryNode
from utils import clamp_shock, country_dict_to_snapshot


def _sanitize_disruptions(
    countries: dict[str, CountryNode],
    disruptions: dict[str, float],
) -> dict[str, float]:
    """Return valid disruptions clamped into [0.0, 1.0]."""
    return {
        code: clamp_shock(impact)
        for code, impact in disruptions.items()
        if code in countries and clamp_shock(impact) > 0.0
    }


def _compute_trade_pressures(
    countries: dict[str, CountryNode],
    disruptions: dict[str, float],
    trade_pressure_scale: float,
) -> dict[str, float]:
    """Return import pressure created by the currently disrupted exporters."""
    pressures = {code: 0.0 for code in countries}

    for exporter_code, disruption in disruptions.items():
        exporter = countries[exporter_code]
        for importer, weight in exporter.trading_partners.items():
            pressures[importer.code] += disruption * weight * trade_pressure_scale

    return {
        code: clamp_shock(total_pressure)
        for code, total_pressure in pressures.items()
        if total_pressure > 0.0
    }


def _apply_substitution_and_inventory(
    countries: dict[str, CountryNode],
    import_pressures: dict[str, float],
    inventories: dict[str, float],
    substitution_rate: float | Mapping[str, float],
    delay_share: float | Mapping[str, float],
    substitution_pressure_exponent: float,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Return immediate shortages, updated inventory levels, and delayed shortages.

    Substitution becomes less effective for larger shortages, and some unresolved
    shortage is deferred to the next step rather than hitting immediately.
    """
    remaining_inventories = dict(inventories)
    immediate_shortages = {}
    deferred_shortages = {}

    for code in countries:
        pressure = clamp_shock(import_pressures.get(code, 0.0))
        if pressure <= 0.0:
            continue

        base_substitution_rate = clamp_shock(_profile_value(substitution_rate, code))
        effective_substitution_rate = base_substitution_rate * (
            1.0 - pressure ** max(0.1, substitution_pressure_exponent)
        )
        shortage_after_substitution = max(0.0, pressure * (1.0 - effective_substitution_rate))
        inventory_used = min(remaining_inventories[code], shortage_after_substitution)
        remaining_inventories[code] -= inventory_used

        remaining_shortage = clamp_shock(shortage_after_substitution - inventory_used)
        if remaining_shortage > 0.0:
            country_delay_share = clamp_shock(_profile_value(delay_share, code))
            deferred_amount = clamp_shock(remaining_shortage * country_delay_share)
            immediate_amount = clamp_shock(remaining_shortage - deferred_amount)
            if immediate_amount > 0.0:
                immediate_shortages[code] = immediate_amount
            if deferred_amount > 0.0:
                deferred_shortages[code] = deferred_amount

    return immediate_shortages, remaining_inventories, deferred_shortages


def _apply_health_updates(
    countries: dict[str, CountryNode],
    disruptions: dict[str, float],
    shortages: dict[str, float],
    health_damage_scale: float,
    shortage_damage_scale: float,
) -> None:
    """Apply current disruptions and shortages to health."""
    for code, country in countries.items():
        disruption = clamp_shock(disruptions.get(code, 0.0))
        shortage = clamp_shock(shortages.get(code, 0.0))
        total_damage = clamp_shock(
            disruption * health_damage_scale + shortage * shortage_damage_scale
        )
        if total_damage > 0.0:
            country.apply_shock(total_damage)


def _rebuild_inventories(
    countries: dict[str, CountryNode],
    inventories: dict[str, float],
    disruptions: dict[str, float],
    import_pressures: dict[str, float],
    inventory_rebuild_rate: float,
    max_inventory: float | Mapping[str, float],
) -> dict[str, float]:
    """Restore some inventory when a country is relatively healthy and stable."""
    rebuilt = {}
    for code, country in countries.items():
        disruption = clamp_shock(disruptions.get(code, 0.0))
        pressure = clamp_shock(import_pressures.get(code, 0.0))
        rebuild_amount = inventory_rebuild_rate * country.current_health * (1.0 - max(disruption, pressure))
        rebuilt[code] = min(_profile_value(max_inventory, code), inventories[code] + rebuild_amount)
    return rebuilt


def _compute_next_disruptions(
    countries: dict[str, CountryNode],
    current_disruptions: dict[str, float],
    shortages: dict[str, float],
    threshold: float,
    persistence: float,
) -> dict[str, float]:
    """Return the disruption levels for the next step."""
    next_disruptions = {}

    for code, country in countries.items():
        lingering_disruption = clamp_shock(current_disruptions.get(code, 0.0) * persistence)
        next_impact = clamp_shock(max(shortages.get(code, 0.0), lingering_disruption))
        if next_impact >= threshold and country.current_health > MIN_HEALTH_CUTOFF:
            next_disruptions[code] = next_impact

    return dict(sorted(next_disruptions.items()))


def _snapshot(values: dict[str, float]) -> dict[str, float]:
    """Return a sorted shallow snapshot of scalar values."""
    return {code: values[code] for code in sorted(values)}


def _combine_pressures(
    first_pressures: dict[str, float],
    second_pressures: dict[str, float],
) -> dict[str, float]:
    """Return the summed pressure map after clamping each country's total."""
    combined = {
        code: clamp_shock(first_pressures.get(code, 0.0) + second_pressures.get(code, 0.0))
        for code in set(first_pressures) | set(second_pressures)
    }
    return {code: value for code, value in combined.items() if value > 0.0}


def _profile_value(profile: float | Mapping[str, float], code: str) -> float:
    """Return either a scalar profile value or a code-specific value."""
    if isinstance(profile, Mapping):
        return float(profile.get(code, 0.0))
    return float(profile)


def run_time_step_simulation(
    countries: dict[str, CountryNode],
    initial_shocks: dict[str, float],
    threshold: float = DEFAULT_THRESHOLD,
    max_steps: int = DEFAULT_TIME_STEPS,
    inventory_buffer: float | Mapping[str, float] = DEFAULT_INVENTORY_BUFFER,
    substitution_rate: float | Mapping[str, float] = SUBSTITUTION_RATE,
    delay_share: float | Mapping[str, float] = SHORTAGE_DELAY_SHARE,
    trade_pressure_scale: float = TRADE_PRESSURE_SCALE,
    inventory_rebuild_rate: float = INVENTORY_REBUILD_RATE,
    health_damage_scale: float = HEALTH_DAMAGE_SCALE,
    shortage_damage_scale: float = SHORTAGE_DAMAGE_SCALE,
    persistence: float = DISRUPTION_PERSISTENCE,
    substitution_pressure_exponent: float = SUBSTITUTION_PRESSURE_EXPONENT,
) -> list[dict[str, Any]]:
    """Run the time-step simulation and return replay-friendly snapshots."""
    step_history = []
    current_disruptions = _sanitize_disruptions(countries, initial_shocks)
    if max_steps <= 0 or not current_disruptions:
        return step_history

    inventories = {code: _profile_value(inventory_buffer, code) for code in countries}
    deferred_shortages = {code: 0.0 for code in countries}

    for step in range(max_steps):
        trade_pressures = _compute_trade_pressures(countries, current_disruptions, trade_pressure_scale)
        import_pressures = _combine_pressures(trade_pressures, deferred_shortages)
        shortages, depleted_inventories, deferred_shortages = _apply_substitution_and_inventory(
            countries,
            import_pressures,
            inventories,
            substitution_rate,
            delay_share,
            substitution_pressure_exponent,
        )
        _apply_health_updates(
            countries,
            current_disruptions,
            shortages,
            health_damage_scale,
            shortage_damage_scale,
        )
        inventories = _rebuild_inventories(
            countries,
            depleted_inventories,
            current_disruptions,
            import_pressures,
            inventory_rebuild_rate,
            inventory_buffer,
        )

        step_history.append(
            {
                "step": step,
                "shock_data": dict(sorted(current_disruptions.items())),
                "health_data": country_dict_to_snapshot(countries),
                "inventory_data": _snapshot(inventories),
                "pressure_data": _snapshot(import_pressures),
                "shortage_data": _snapshot(shortages),
                "deferred_shortage_data": _snapshot(
                    {code: value for code, value in deferred_shortages.items() if value > 0.0}
                ),
            }
        )

        current_disruptions = _compute_next_disruptions(
            countries,
            current_disruptions,
            shortages,
            threshold,
            persistence,
        )
        if not current_disruptions and not any(value > 0.0 for value in deferred_shortages.values()):
            break

    return step_history
