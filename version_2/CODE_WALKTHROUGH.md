# Version 2 Code Walkthrough

This document explains exactly how `version_2` runs, from startup to simulation to visualization.

It is written against the current code in this folder, not the older `version_1` model.

## 1. High-Level Idea

`version_2` is a repeated time-step trade-shock simulation.

The model says:

1. Some countries start with an initial disruption.
2. Disrupted exporters create trade pressure on their import partners.
3. Importers try to absorb that pressure through substitution and inventory.
4. Some unresolved shortage hits immediately, and some is delayed into the next step.
5. Countries lose health from disruption and shortages.
6. The process repeats for a fixed number of steps.

This is still a simplified model, but it is more realistic than a pure wave-spreading model because:

- trade dependence is based on importer shares, not GDP-normalized edges
- countries have different resilience profiles
- substitution is weaker for large shocks than for small shocks
- shortages can be delayed instead of hitting all at once

## 2. Main Files and Their Jobs

### `main.py`

This is the entry point.

It does two different things depending on the arguments:

- `python main.py`
  - starts the Dash browser interface
- `python main.py --cli`
  - uses the older terminal + Plotly flow

Important functions:

- `parse_arguments()`
  - reads command-line arguments
- `load_project_graph(args)`
  - loads GDP, trade, and coordinate files
  - builds the country graph
- `main()`
  - decides whether to run the dashboard or CLI flow

### `data_parser.py`

This loads and cleans the CSV files.

It handles:

- GDP data from World Bank exports
- bilateral trade data from Comtrade-style exports
- optional country coordinates

Important functions:

- `load_gdp_data(path)`
  - reads 2023 GDP values
  - removes World Bank aggregates using the metadata file when available
- `load_trade_data(path)`
  - reads export rows only
  - keeps only valid ISO-3 country pairs
- `load_country_coordinates(path)`
  - loads country centroids for the map
- `validate_country_matches(gdp_data, trade_data)`
  - checks overlap between GDP and trade datasets

### `country_node.py`

This defines the `CountryNode` class.

Each country stores:

- `code`
- `name`
- `total_gdp`
- `lat`, `lon`
- `total_imports`
- `total_exports`
- `current_health`
- `trading_partners`

Important methods:

- `add_trading_partner(partner, weight)`
  - adds a directed trade edge
- `apply_shock(shock)`
  - damages health multiplicatively
- `reset_health()`
  - resets the country before a new run

### `graph_builder.py`

This file builds the trade graph and computes country-specific resilience proxies.

Important functions:

- `build_country_nodes(...)`
  - creates a `CountryNode` for each GDP country
- `add_trade_edges(...)`
  - adds exporter -> importer edges
  - also accumulates raw `total_imports` and `total_exports`
- `compute_edge_weight(trade_value, importer_total_imports)`
  - returns:
  - `trade_value / importer_total_imports`
  - capped by `MAX_EDGE_WEIGHT`
- `build_trade_graph(...)`
  - builds the full country graph
- `build_country_resilience_profiles(countries)`
  - derives resilience proxies from the trade network
- `clone_trade_graph(countries)`
  - copies the graph for display-only filtering
- `limit_top_k_partners(countries, top_k)`
  - trims edges for display only

### `simulation.py`

This is the core model.

It contains the repeated time-step logic.

Important functions:

- `_compute_trade_pressures(...)`
- `_apply_substitution_and_inventory(...)`
- `_apply_health_updates(...)`
- `_rebuild_inventories(...)`
- `_compute_next_disruptions(...)`
- `run_time_step_simulation(...)`

### `runtime_options.py`

This handles:

- country-name parsing
- multi-country initial shock setup
- visibility selection
- CLI prompts

### `dashboard.py`

This builds the Dash browser app.

It:

- loads the graph once
- runs the simulation when the user presses `Run Simulation`
- stores the simulation result in Dash state
- updates the map when the user moves the step slider or playback buttons

### `visualization.py`

This turns saved simulation snapshots into Plotly figures.

It uses:

- country fills for health
- centroid markers for currently disrupted countries
- optional edges only for active countries

## 3. Startup Flow

When you run:

```bash
python main.py
```

the code path is:

1. `main.py -> parse_arguments()`
2. `main.py -> main()`
3. since `--cli` is not present:
4. `dashboard.run_dashboard(args)`

Inside `run_dashboard(args)`:

1. `_load_base_graph(args)`
2. build country dropdown options
3. create the Dash layout
4. register callbacks
5. choose an available port
6. open the browser automatically
7. start the local Dash server

The graph is loaded only once when the dashboard starts. The simulation itself runs later, when the user presses the button.

## 4. Data Loading and Graph Construction

The dashboard and CLI both use the same graph-loading path.

### 4.1 GDP Loading

`load_gdp_data(path)`:

1. locates the real header row
2. finds the `Country Name`, `Country Code`, and `2023` GDP column
3. optionally reads the matching World Bank metadata file
4. removes aggregate rows
5. returns:

```python
{
    "USA": {"name": "United States", "gdp": ...},
    "CHN": {"name": "China", "gdp": ...},
    ...
}
```

### 4.2 Trade Loading

`load_trade_data(path)`:

1. finds the trade header row
2. identifies reporter/exporter, partner/importer, and trade value columns
3. keeps export rows only
4. removes invalid ISO codes and `World` totals
5. returns rows like:

```python
{
    "exporter_code": "USA",
    "importer_code": "CAN",
    "trade_value": 123456789.0,
}
```

### 4.3 Building Nodes and Edges

`build_trade_graph(gdp_data, trade_data, coordinates)`:

1. creates one `CountryNode` per GDP country
2. computes each importer's total imports
3. for every trade row:
   - increments exporter `total_exports`
   - increments importer `total_imports`
   - computes the edge weight
   - adds exporter -> importer

So the graph is:

- directed
- weighted
- country-to-country

### 4.4 Edge Weight Meaning

The edge weight means:

> "What share of this importer's tracked imports comes from this exporter?"

Example:

- Canada total imports in the dataset: `100`
- imports from the United States: `25`

Then:

```python
USA -> CAN = 0.25
```

So if the US is disrupted, Canada should feel more pressure than if the edge were `0.02`.

## 5. How Resilience Profiles Are Computed

This happens in `graph_builder.py -> build_country_resilience_profiles(countries)`.

Because the project does not have direct inventory or substitution datasets, `version_2` derives proxies from the trade structure itself.

For each importer, the code computes:

- supplier diversification
- largest-supplier concentration
- number of suppliers
- import dependence relative to GDP

### 5.1 Diversification

The code looks at all incoming supplier shares for an importer and computes a concentration score:

```python
concentration = sum(share * share for share in normalized_shares)
effective_partner_count = 1.0 / concentration
```

Then it maps that to a `0.0` to `1.0` diversification score.

Interpretation:

- concentrated importer -> low diversification
- spread-out importer -> high diversification

### 5.2 Import Dependence

The code also uses:

```python
import_dependency = total_imports / total_gdp
```

then scales and clamps it into `[0, 1]`.

Interpretation:

- higher import dependence -> more fragile

### 5.3 Derived Profiles

From those values, the model computes:

- `substitution_rates`
  - how easily a country can replace missing imports
- `inventory_buffers`
  - how much shortage it can absorb
- `delay_shares`
  - how much unresolved shortage gets pushed into later steps

These are **not** measured real inventory datasets.
They are **proxies derived from the trade network and GDP data**.

## 6. The Simulation Loop

The main simulation function is:

```python
run_time_step_simulation(...)
```

It returns a `step_history` list. Each item is a snapshot dictionary for one time step.

### 6.1 Inputs

It receives:

- `countries`
- `initial_shocks`
- `threshold`
- `max_steps`
- country-specific or scalar:
  - `inventory_buffer`
  - `substitution_rate`
  - `delay_share`

and global scalars like:

- `trade_pressure_scale`
- `health_damage_scale`
- `shortage_damage_scale`
- `persistence`

### 6.2 Initial Setup

At the start:

- `current_disruptions` is built from the initial shock countries
- `inventories` starts from the country inventory profile
- `deferred_shortages` starts at zero for every country

### 6.3 One Full Step

Each loop iteration does the following.

#### Step A: Compute trade pressure

`_compute_trade_pressures(...)`

For each currently disrupted exporter:

```python
pressure += disruption * edge_weight * trade_pressure_scale
```

This creates raw import pressure on the importers.

Then the code combines:

- new trade pressure from this step
- deferred shortage carried from the previous step

with `_combine_pressures(...)`.

So total pressure is:

```python
total_pressure = current_trade_pressure + carried_shortage_from_last_step
```

#### Step B: Apply substitution and inventory

`_apply_substitution_and_inventory(...)`

This is where the model became more realistic.

It now does three things:

1. **Nonlinear substitution**

Base substitution is country-specific, but it is reduced when pressure is large:

```python
effective_substitution_rate = base_substitution_rate * (1 - pressure ** exponent)
```

Interpretation:

- small shock -> easier to reroute
- large shock -> much harder to reroute

2. **Inventory absorption**

After substitution, remaining shortage can be absorbed by inventory:

```python
inventory_used = min(current_inventory, remaining_shortage)
```

3. **Delayed shortage**

Any shortage that remains is split into:

- immediate shortage
- deferred shortage

using the country's delay share.

So unresolved shortage does not always hit all at once.

#### Step C: Update health

`_apply_health_updates(...)`

A country's health is damaged by:

- current disruption
- some current shortage

The damage term is:

```python
total_damage = disruption * health_damage_scale + shortage * shortage_damage_scale
```

#### Step D: Rebuild inventory

`_rebuild_inventories(...)`

Countries rebuild some inventory if they are:

- healthier
- under lower disruption
- under lower pressure

So inventory does not instantly refill during a crisis.

#### Step E: Save the snapshot

Each step stores:

- `step`
- `shock_data`
- `health_data`
- `inventory_data`
- `pressure_data`
- `shortage_data`
- `deferred_shortage_data`

Interpretation:

- `shock_data`
  - currently active disruptions
- `pressure_data`
  - total pressure this step before absorption
- `shortage_data`
  - immediate unresolved shortage after substitution/inventory
- `deferred_shortage_data`
  - unresolved shortage pushed into the next step

#### Step F: Compute next disruptions

`_compute_next_disruptions(...)`

Next-step disruption is the maximum of:

- immediate shortage
- lingering disruption from the previous step
- optional health-gap pass-through

Right now, health-gap pass-through is configured as `0.0`, so it is effectively disabled by default.

That was an intentional fix, because the older feedback loop forced countries toward an artificial common health floor.

## 7. Why the Simulation Now Uses All Requested Time Steps

The simulation no longer stops early when disruptions disappear.

It continues until `max_steps`, which means:

- early steps can show crisis spread
- later steps can show inventory rebuilding and a stable post-shock state

This matters for the dashboard slider, because now changing `Time steps` actually changes how many steps you can inspect.

## 8. Dashboard Execution Flow

In `dashboard.py`, the important parts are:

### 8.1 `_run_simulation_from_controls(...)`

When the user presses `Run Simulation`, this function:

1. clones the base graph
2. resets health
3. reads selected countries and shock values
4. builds resilience profiles
5. runs the simulation
6. computes visible countries
7. returns:

```python
{
    "step_history": ...,
    "visible_codes": ...,
    "top_k": ...,
}
```

### 8.2 Figure rendering

The dashboard does not rerun the simulation when the user moves the slider.

Instead:

1. the simulation result is stored in `dcc.Store`
2. the slider chooses a `step_index`
3. `_render_dashboard_figure(...)` rebuilds the figure for that step only

That makes the UI more stable and easier to reason about.

### 8.3 Playback

Dash-native previous / next / play / pause controls update the slider.

The slider value is the current displayed step.

## 9. Visualization Logic

`visualization.py` has two main paths:

- `create_step_figure(...)`
  - used by the dashboard
- `create_simulation_figure(...)`
  - used by the old CLI Plotly replay mode

### 9.1 Country colors

Each visible country is colored by health.

- low health -> red/orange
- high health -> green

### 9.2 Active markers

Marker circles are drawn only for countries in `shock_data`.

Those markers show current disruption intensity.

### 9.3 Edges

Edges are only drawn when they touch countries currently active in:

- `shock_data`
- or the current shortage set used for activity

This keeps the map from becoming unreadable.

## 10. What the Important Numbers Mean

### `current_health`

This is not "national well-being" in a broad sense.

In this model, it is closer to:

> overall import-dependent productive condition

`1.0` means undamaged.
Lower values mean the country is more disrupted.

### `shock_data`

This is the currently active disruption level used to spread effects to partners.

### `pressure_data`

This is the total pressure hitting the importer this step, before absorption.

### `shortage_data`

This is the shortage that remains after substitution and inventory use.

### `deferred_shortage_data`

This is the shortage that is carried into the next step rather than hitting immediately.

## 11. What Changed Compared to Earlier Version 2

The current model is more realistic than the earlier `version_2` state because it now has:

- country-specific import/export totals stored on nodes
- better resilience proxies from diversification and import dependence
- nonlinear substitution instead of a flat percentage
- delayed shortage carryover
- mild same-step shortage damage
- a disabled default health-gap feedback loop, which removed the artificial `0.331` health floor problem

## 12. What Is Still Simplified

Even after these improvements, the model is still a simplified trade-shock model.

It still does **not** directly model:

- sector-level trade
- energy vs food vs finance separately
- prices and inflation
- policy response
- direct measured national inventories
- supply-chain data below the country level

So the best interpretation is:

> this is a country-level trade-dependence simulation with inferred resilience proxies, not a real forecasting model.

## 13. Recommended Way to Explain It

If you need to explain the code quickly:

> `version_2` builds a directed trade graph from real GDP and bilateral trade data.  
> Each edge measures how dependent an importer is on a specific exporter.  
> The simulation runs in time steps. In each step, disrupted exporters create import pressure, countries absorb part of it through substitution and inventory, some shortage is delayed, and remaining shortage becomes new disruption.  
> The dashboard just replays those saved step snapshots.
