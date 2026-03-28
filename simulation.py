"""Time-step trade disruption simulation with buffering and persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any

from config import (
    DEMAND_PRESSURE_SCALE,
    DEFAULT_INVENTORY_BUFFER,
    DEFAULT_THRESHOLD,
    DEFAULT_TIME_STEPS,
    DISRUPTION_PERSISTENCE,
    HEALTH_DAMAGE_SCALE,
    INVENTORY_REBUILD_RATE,
    INVENTORY_STRESS_EXPONENT,
    INVENTORY_STRESS_PENALTY,
    MIN_HEALTH_CUTOFF,
    SHORTAGE_DAMAGE_SCALE,
    SHORTAGE_DELAY_SHARE,
    SUBSTITUTION_RATE,
    SUBSTITUTION_CONCENTRATION_PENALTY,
    SUBSTITUTION_PRESSURE_EXPONENT,
    TRADE_PRESSURE_SCALE,
)
from country_node import CountryNode
from utils import clamp_shock, country_dict_to_snapshot

PressureMap = dict[str, float]
PressureSources = dict[str, dict[str, float]]


@dataclass(frozen=True)
class SimulationProfiles:
    """Resolved per-country profile values used during a simulation run."""

    inventory_buffer: PressureMap
    substitution_rate: PressureMap
    delay_share: PressureMap


@dataclass
class StepState:
    """Mutable state carried from one simulation step to the next."""

    disruptions: PressureMap
    inventories: PressureMap
    deferred_shortages: PressureMap
    pressures: PressureMap = field(default_factory=dict)
    pressure_sources: PressureSources = field(default_factory=dict)
    shortages: PressureMap = field(default_factory=dict)


@dataclass(frozen=True)
class ShortageResult:
    """Shortages and inventory left after substitution and buffering."""

    immediate_shortages: PressureMap
    remaining_inventories: PressureMap
    deferred_shortages: PressureMap


def _sanitize_disruptions(
    countries: dict[str, CountryNode],
    disruptions: dict[str, float],
) -> dict[str, float]:
    """Return valid disruptions clamped into [0.0, 1.0]."""
    return {
        country_code: clamp_shock(impact)
        for country_code, impact in disruptions.items()
        if country_code in countries and clamp_shock(impact) > 0.0
    }


def _compute_trade_pressures(
    countries: dict[str, CountryNode],
    disruptions: PressureMap,
    trade_pressure_scale: float,
    demand_pressure_scale: float,
) -> tuple[PressureMap, PressureSources]:
    """Return bilateral pressure totals and per-source contributions."""
    pressures: PressureMap = {}
    pressure_sources: PressureSources = {}
    for country_code in countries:
        pressures[country_code] = 0.0
        pressure_sources[country_code] = {}

    for exporter in countries.values():
        exporter_disruption = clamp_shock(disruptions.get(exporter.code, 0.0))
        for importer, weights in exporter.trading_partners.items():
            supply_weight = float(weights["supply_weight"])
            demand_weight = float(weights["demand_weight"])
            importer_disruption = clamp_shock(disruptions.get(importer.code, 0.0))

            if exporter_disruption > 0.0 and supply_weight > 0.0:
                contribution = exporter_disruption * supply_weight * trade_pressure_scale
                pressures[importer.code] += contribution
                pressure_sources[importer.code][exporter.code] = (
                    pressure_sources[importer.code].get(exporter.code, 0.0) + contribution
                )

            if importer_disruption > 0.0 and demand_weight > 0.0:
                contribution = importer_disruption * demand_weight * demand_pressure_scale
                pressures[exporter.code] += contribution
                pressure_sources[exporter.code][importer.code] = (
                    pressure_sources[exporter.code].get(importer.code, 0.0) + contribution
                )

    clamped_pressures: PressureMap = {}
    clamped_sources: PressureSources = {}
    for code, total_pressure in pressures.items():
        clamped_total = clamp_shock(total_pressure)
        if clamped_total <= 0.0:
            continue

        source_totals = pressure_sources[code]
        source_sum = sum(source_totals.values())
        if source_sum > 0.0 and clamped_total < source_sum:
            scale = clamped_total / source_sum
            clamped_sources[code] = {
                source_code: value * scale
                for source_code, value in source_totals.items()
                if value > 0.0
            }
        else:
            clamped_sources[code] = {
                source_code: value for source_code, value in source_totals.items() if value > 0.0
            }
        clamped_pressures[code] = clamped_total

    return clamped_pressures, clamped_sources


def _pressure_concentration(source_pressures: Mapping[str, float]) -> float:
    """Return Herfindahl-style concentration for incoming pressure shares."""
    total_pressure = sum(source_pressures.values())
    if total_pressure <= 0.0:
        return 0.0

    return clamp_shock(
        sum((pressure / total_pressure) ** 2 for pressure in source_pressures.values() if pressure > 0.0)
    )


def _apply_substitution_and_inventory(
    countries: dict[str, CountryNode],
    import_pressures: PressureMap,
    pressure_sources: Mapping[str, Mapping[str, float]],
    inventories: PressureMap,
    profiles: SimulationProfiles,
    substitution_pressure_exponent: float,
    substitution_concentration_penalty: float,
    inventory_stress_penalty: float,
    inventory_stress_exponent: float,
) -> ShortageResult:
    """Return immediate shortages, updated inventory levels, and delayed shortages.

    Substitution becomes less effective for larger shortages, and some unresolved
    shortage is deferred to the next step rather than hitting immediately.
    """
    remaining_inventories = dict(inventories)
    immediate_shortages: PressureMap = {}
    deferred_shortages: PressureMap = {}

    for code in countries:
        pressure = clamp_shock(import_pressures.get(code, 0.0))
        if pressure <= 0.0:
            continue

        base_substitution_rate = clamp_shock(profiles.substitution_rate[code])
        concentration = _pressure_concentration(pressure_sources.get(code, {}))
        concentration_multiplier = 1.0 - (
            clamp_shock(substitution_concentration_penalty) * concentration
        )
        effective_substitution_rate = base_substitution_rate * concentration_multiplier * (
            1.0 - pressure ** max(0.1, substitution_pressure_exponent)
        )
        shortage_after_substitution = max(0.0, pressure * (1.0 - effective_substitution_rate))
        usable_inventory_share = 1.0 - (
            clamp_shock(inventory_stress_penalty)
            * (pressure ** max(0.1, inventory_stress_exponent))
        )
        usable_inventory = remaining_inventories[code] * max(0.0, usable_inventory_share)
        inventory_used = min(usable_inventory, shortage_after_substitution)
        remaining_inventories[code] -= inventory_used

        remaining_shortage = clamp_shock(shortage_after_substitution - inventory_used)
        if remaining_shortage > 0.0:
            country_delay_share = clamp_shock(profiles.delay_share[code])
            deferred_amount = clamp_shock(remaining_shortage * country_delay_share)
            immediate_amount = clamp_shock(remaining_shortage - deferred_amount)
            if immediate_amount > 0.0:
                immediate_shortages[code] = immediate_amount
            if deferred_amount > 0.0:
                deferred_shortages[code] = deferred_amount

    return ShortageResult(
        immediate_shortages=immediate_shortages,
        remaining_inventories=remaining_inventories,
        deferred_shortages=deferred_shortages,
    )


def _apply_health_updates(
    countries: dict[str, CountryNode],
    disruptions: PressureMap,
    shortages: PressureMap,
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
    inventories: PressureMap,
    disruptions: PressureMap,
    import_pressures: PressureMap,
    inventory_rebuild_rate: float,
    max_inventory: PressureMap,
) -> PressureMap:
    """Restore some inventory when a country is relatively healthy and stable."""
    rebuilt: PressureMap = {}
    for code, country in countries.items():
        disruption = clamp_shock(disruptions.get(code, 0.0))
        pressure = clamp_shock(import_pressures.get(code, 0.0))
        rebuild_amount = inventory_rebuild_rate * country.current_health * (1.0 - max(disruption, pressure))
        rebuilt[code] = min(max_inventory[code], inventories[code] + rebuild_amount)
    return rebuilt


def _compute_next_disruptions(
    countries: dict[str, CountryNode],
    current_disruptions: PressureMap,
    shortages: PressureMap,
    threshold: float,
    persistence: float,
) -> PressureMap:
    """Return the disruption levels for the next step."""
    next_disruptions: PressureMap = {}

    for code, country in countries.items():
        lingering_disruption = clamp_shock(current_disruptions.get(code, 0.0) * persistence)
        next_impact = clamp_shock(max(shortages.get(code, 0.0), lingering_disruption))
        if next_impact >= threshold and country.current_health > MIN_HEALTH_CUTOFF:
            next_disruptions[code] = next_impact

    return dict(sorted(next_disruptions.items()))


def _snapshot(values: PressureMap) -> PressureMap:
    """Return a sorted shallow snapshot of scalar values."""
    return {
        country_code: values[country_code]
        for country_code in sorted(values)
    }


def _combine_pressures(
    first_pressures: PressureMap,
    second_pressures: PressureMap,
) -> PressureMap:
    """Return the summed pressure map after clamping each country's total."""
    combined = {
        country_code: clamp_shock(
            first_pressures.get(country_code, 0.0) + second_pressures.get(country_code, 0.0)
        )
        for country_code in set(first_pressures) | set(second_pressures)
    }
    return {
        country_code: value
        for country_code, value in combined.items()
        if value > 0.0
    }


def _profile_value(profile: float | Mapping[str, float], code: str) -> float:
    """Return either a scalar profile value or a code-specific value."""
    if isinstance(profile, Mapping):
        return float(profile.get(code, 0.0))
    return float(profile)


def _resolve_profiles(
    countries: dict[str, CountryNode],
    inventory_buffer: float | Mapping[str, float],
    substitution_rate: float | Mapping[str, float],
    delay_share: float | Mapping[str, float],
) -> SimulationProfiles:
    """Resolve scalar-or-mapping profiles into per-country dictionaries once."""
    codes = countries.keys()
    return SimulationProfiles(
        inventory_buffer={
            country_code: _profile_value(inventory_buffer, country_code)
            for country_code in codes
        },
        substitution_rate={
            country_code: _profile_value(substitution_rate, country_code)
            for country_code in codes
        },
        delay_share={
            country_code: _profile_value(delay_share, country_code)
            for country_code in codes
        },
    )


def _build_step_snapshot(
    step: int,
    countries: dict[str, CountryNode],
    state: StepState,
) -> dict[str, Any]:
    """Return the replay-friendly snapshot for one completed simulation step."""
    return {
        "step": step,
        "shock_data": dict(sorted(state.disruptions.items())),
        "health_data": country_dict_to_snapshot(countries),
        "inventory_data": _snapshot(state.inventories),
        "pressure_data": _snapshot(state.pressures),
        "shortage_data": _snapshot(state.shortages),
        "deferred_shortage_data": _snapshot(
            {
                country_code: value
                for country_code, value in state.deferred_shortages.items()
                if value > 0.0
            }
        ),
    }


def run_time_step_simulation(
    countries: dict[str, CountryNode],
    initial_shocks: dict[str, float],
    threshold: float = DEFAULT_THRESHOLD,
    max_steps: int = DEFAULT_TIME_STEPS,
    inventory_buffer: float | Mapping[str, float] = DEFAULT_INVENTORY_BUFFER,
    substitution_rate: float | Mapping[str, float] = SUBSTITUTION_RATE,
    delay_share: float | Mapping[str, float] = SHORTAGE_DELAY_SHARE,
    trade_pressure_scale: float = TRADE_PRESSURE_SCALE,
    demand_pressure_scale: float = DEMAND_PRESSURE_SCALE,
    inventory_rebuild_rate: float = INVENTORY_REBUILD_RATE,
    health_damage_scale: float = HEALTH_DAMAGE_SCALE,
    shortage_damage_scale: float = SHORTAGE_DAMAGE_SCALE,
    persistence: float = DISRUPTION_PERSISTENCE,
    substitution_pressure_exponent: float = SUBSTITUTION_PRESSURE_EXPONENT,
    substitution_concentration_penalty: float = SUBSTITUTION_CONCENTRATION_PENALTY,
    inventory_stress_penalty: float = INVENTORY_STRESS_PENALTY,
    inventory_stress_exponent: float = INVENTORY_STRESS_EXPONENT,
) -> list[dict[str, Any]]:
    """Run the time-step simulation and return replay-friendly snapshots."""
    step_history = []
    profiles = _resolve_profiles(countries, inventory_buffer, substitution_rate, delay_share)
    initial_disruptions = _sanitize_disruptions(countries, initial_shocks)
    if max_steps <= 0 or not initial_disruptions:
        return step_history

    state = StepState(
        disruptions=initial_disruptions,
        inventories=dict(profiles.inventory_buffer),
        deferred_shortages={country_code: 0.0 for country_code in countries},
    )

    for step in range(max_steps):
        trade_pressures, state.pressure_sources = _compute_trade_pressures(
            countries,
            state.disruptions,
            trade_pressure_scale,
            demand_pressure_scale,
        )
        combined_pressures = _combine_pressures(trade_pressures, state.deferred_shortages)
        state.pressures = combined_pressures
        shortage_result = _apply_substitution_and_inventory(
            countries,
            combined_pressures,
            state.pressure_sources,
            state.inventories,
            profiles,
            substitution_pressure_exponent,
            substitution_concentration_penalty,
            inventory_stress_penalty,
            inventory_stress_exponent,
        )
        state.shortages = shortage_result.immediate_shortages
        state.deferred_shortages = shortage_result.deferred_shortages
        _apply_health_updates(
            countries,
            state.disruptions,
            state.shortages,
            health_damage_scale,
            shortage_damage_scale,
        )
        state.inventories = _rebuild_inventories(
            countries,
            shortage_result.remaining_inventories,
            state.disruptions,
            combined_pressures,
            inventory_rebuild_rate,
            profiles.inventory_buffer,
        )
        step_history.append(_build_step_snapshot(step, countries, state))
        state.disruptions = _compute_next_disruptions(
            countries,
            state.disruptions,
            state.shortages,
            threshold,
            persistence,
        )
        if not state.disruptions and not any(
            value > 0.0 for value in state.deferred_shortages.values()
        ):
            break

    return step_history


if __name__ == "__main__":
    import doctest
    import python_ta
    from pyta_config import PYTA_CONFIG

    doctest.testmod()
    python_ta.check_all(config=PYTA_CONFIG)
