# `version_2` Code Walkthrough

This file explains how the `version_2` code works, in order, from startup to visualization.

The goal is to make the actual code easier to understand, not just to describe the model at a high level.

---

## 1. Big Picture

The program does this:

1. `main.py` parses command-line arguments and starts the dashboard.
2. `dashboard.py` loads the real CSV data and builds the trade graph.
3. `graph_builder.py` creates `CountryNode` objects and trade edges.
4. `graph_builder.py` also computes resilience profiles from the trade network.
5. `simulation.py` runs the time-step shock simulation.
6. `visualization.py` turns the saved step history into a Plotly map.

So the actual execution path is:

```text
main.py
-> dashboard.py
-> data_parser.py
-> graph_builder.py
-> simulation.py
-> visualization.py
```

---

## 2. `main.py`

File: [version_2/main.py](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/main.py)

This file is very small. It only does 2 things:

### `parse_arguments()`

This creates the command-line options for:

- GDP file path
- trade file path
- coordinate file path
- default selected countries
- threshold
- visible country count
- visible edge count
- port
- whether edges start hidden

Example:

```bash
python3 main.py --threshold 0.003 --top-n 150 --top-k 40
```

### `main()`

This calls:

```python
from dashboard import run_dashboard
run_dashboard(args)
```

So `main.py` does **not** run the simulation itself. It just launches the UI.

---

## 3. `country_node.py`

File: [version_2/country_node.py](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/country_node.py)

This file defines the main object used in the graph:

```python
class CountryNode:
```

Each country stores:

- `code`
  - ISO-3 code like `USA`, `CHN`, `JPN`
- `name`
  - full country name
- `total_gdp`
- `lat`, `lon`
  - map coordinates
- `total_imports`
- `total_exports`
- `current_health`
  - current condition of the country in the simulation
- `trading_partners`
  - outgoing edges to other `CountryNode`s

### `trading_partners`

This is important.

It is not just:

```python
partner -> weight
```

It is:

```python
partner -> {
    "supply_weight": ...,
    "demand_weight": ...
}
```

So one bilateral trade connection stores **two** effects:

- `supply_weight`
  - how much the importer depends on the exporter
- `demand_weight`
  - how much the exporter depends on the importer as a buyer

### `add_trading_partner(...)`

This stores the bilateral relationship on one directed edge.

Example:

```python
usa.add_trading_partner(canada, supply_weight=0.25, demand_weight=0.10)
```

Meaning:

- Canada gets 25% supply-side exposure to the USA through this edge
- the USA gets 10% buyer-side exposure to Canada through the same edge

### `apply_shock(...)`

This reduces health multiplicatively:

```python
self.current_health = self.current_health * (1.0 - bounded_shock)
```

Example:

- current health = `0.9`
- shock = `0.2`

Then:

```python
0.9 * (1 - 0.2) = 0.72
```

So this country becomes less healthy after damage.

### `__hash__` and `__eq__`

These exist because `CountryNode` objects are used as dictionary keys in `trading_partners`.

---

## 4. `data_parser.py`

File: [version_2/data_parser.py](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/data_parser.py)

This file loads the CSV files and cleans them.

### `clean_country_codes(code)`

This checks whether a country code looks like a valid ISO-3 code:

```python
if len(cleaned) == 3 and cleaned.isalpha():
```

So:

- `USA` is valid
- `US1` is not
- `W00` is not

### `_read_csv_rows(path)`

This reads a CSV file using a few encodings:

- `utf-8-sig`
- `cp1252`
- `latin-1`

That makes the parser more robust to different CSV downloads.

### `_find_header_index(...)`

Some CSVs have metadata lines before the real header row.

This function scans the file until it finds the row that actually contains the required columns.

### `load_gdp_data(path)`

This loads World Bank GDP data.

It:

- finds the real header
- finds the `2023` GDP column
- filters invalid rows
- removes aggregate rows such as `World`, `High income`, etc.

Result:

```python
{
    "USA": {"name": "United States", "gdp": ...},
    "JPN": {"name": "Japan", "gdp": ...},
}
```

### `load_trade_data(path)`

This loads Comtrade bilateral export rows.

Each usable row becomes:

```python
{
    "exporter_code": "CHN",
    "exporter_name": "China",
    "importer_code": "CAN",
    "importer_name": "Canada",
    "trade_value": 123456789.0,
}
```

Important filters:

- only export rows
- no world-total rows
- valid exporter/importer country codes
- positive trade value

### `load_country_coordinates(path)`

This loads lat/lon coordinates for the map.

If the coordinate file is missing, it just returns `{}` instead of crashing.

### `validate_country_matches(gdp_data, trade_data)`

This is used mainly for diagnostics in the dashboard.

It checks how many country codes overlap between GDP and trade data.

---

## 5. `graph_builder.py`

File: [version_2/graph_builder.py](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/graph_builder.py)

This file turns cleaned rows into the actual graph.

### `build_country_nodes(...)`

This creates one `CountryNode` per GDP country.

At this point:

- nodes exist
- edges do not exist yet

### `compute_supply_weight(trade_value, importer_total_imports)`

Formula:

```python
trade_value / importer_total_imports
```

Meaning:

- what share of the importer's imports comes from this exporter?

Example:

- Canada imports `100`
- `25` comes from the USA

Then:

```python
USA -> CAN supply_weight = 25 / 100 = 0.25
```

### `compute_demand_weight(trade_value, exporter_total_exports)`

Formula:

```python
trade_value / exporter_total_exports
```

Meaning:

- what share of the exporter's exports goes to this importer?

Example:

- USA exports `200`
- `20` goes to Canada

Then:

```python
USA -> CAN demand_weight = 20 / 200 = 0.10
```

### `_compute_import_totals(...)` and `_compute_export_totals(...)`

These compute:

- total imports per country
- total exports per country

Those totals are needed before weights can be calculated.

### `add_trade_edges(...)`

This is where each trade row becomes an edge.

For each row:

1. compute supply weight
2. compute demand weight
3. add the importer/exporter totals to the nodes
4. call:

```python
exporter.add_trading_partner(importer, supply_weight, demand_weight)
```

So one exporter-to-importer edge stores both bilateral effects.

### `build_trade_graph(...)`

This just combines:

- `build_country_nodes(...)`
- `add_trade_edges(...)`

### `clone_trade_graph(...)`

This makes a detached copy of the graph.

That is useful because:

- the simulation should use the full graph
- the display graph may be pruned for visualization

So the dashboard clones the base graph before filtering visible edges.

### `reset_all_countries(...)`

This sets every country's `current_health` back to `1.0`.

That matters because each simulation run mutates the country objects.

### Visibility ranking helpers

These functions decide which countries are shown:

- `get_top_countries_by_gdp(...)`
- `get_visible_country_codes(...)`
- `_rank_countries_by_metric(...)`
- `get_visible_country_codes_by_metric(...)`

Current default display ranking is by total trade, not GDP.

### `build_country_resilience_profiles(...)`

This is one of the most important computations in the code.

It derives country-specific resilience values using only the trade graph.

It computes, for each country:

- supplier diversification
- largest-supplier concentration
- import dependence relative to GDP
- number of active suppliers

Then it creates:

- `substitution_rates`
- `inventory_buffers`
- `delay_shares`

These are **not downloaded directly** from a resilience dataset.
They are inferred from trade structure.

#### Example logic

If a country imports from many partners fairly evenly:

- diversification is high
- largest supplier share is lower
- substitution rate is higher
- inventory buffer is higher
- delay share is higher

If a country relies on only one or two suppliers:

- concentration is higher
- substitution is lower
- inventory is lower

### `limit_top_k_partners(...)`

This prunes each country's outgoing edge list for display.

It sorts by:

```python
supply_weight + demand_weight
```

and keeps only the top `k`.

This is for visualization clarity, not for the actual simulation graph.

---

## 6. `simulation.py`

File: [version_2/simulation.py](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/simulation.py)

This file is the core of the model.

### High-level idea

Each simulation step does:

1. compute new pressure from currently disrupted countries
2. combine that with deferred shortage from the last step
3. apply substitution and inventory
4. turn leftover shortage into damage
5. rebuild some inventory
6. compute next-step disruptions

### Small helper types

This file now uses a cleaner structure:

- `SimulationProfiles`
  - resolved per-country values for:
    - inventory buffer
    - substitution rate
    - delay share
- `StepState`
  - the mutable state of one simulation step
- `ShortageResult`
  - result of the buffering stage

This makes the simulation easier to follow than passing raw parallel dictionaries around everywhere.

### `SimulationProfiles`

This stores:

```python
inventory_buffer
substitution_rate
delay_share
```

all as code-to-float dictionaries.

That means the simulation no longer has to repeatedly check:

- is this profile a scalar?
- or is it a country-specific mapping?

### `StepState`

This holds:

- `disruptions`
- `inventories`
- `deferred_shortages`
- `pressures`
- `pressure_sources`
- `shortages`

So one object represents the current evolving step state.

### `_sanitize_disruptions(...)`

This clamps the initial shocks into `[0.0, 1.0]` and removes invalid country codes.

Example:

```python
{"USA": 1.5, "BAD": 0.2}
```

becomes something like:

```python
{"USA": 1.0}
```

### `_compute_trade_pressures(...)`

This computes both:

- total pressure per country
- source-by-source pressure contributions

That second part matters because substitution now depends on concentration of incoming pressure.

#### Supply-side effect

If exporter `A` is disrupted:

```python
pressure_on_importer += exporter_disruption * supply_weight * trade_pressure_scale
```

#### Demand-side effect

If importer `B` is disrupted:

```python
pressure_on_exporter += importer_disruption * demand_weight * demand_pressure_scale
```

So the model spreads both ways:

- exporter down -> importers lose supply
- importer down -> exporters lose demand

#### Example

Suppose:

- Japan disruption = `0.5`
- `JPN -> THA supply_weight = 0.2`
- `trade_pressure_scale = 0.95`

Then Thailand gets supply pressure:

```python
0.5 * 0.2 * 0.95 = 0.095
```

If Thailand were disrupted instead, and:

- `JPN -> THA demand_weight = 0.1`
- `demand_pressure_scale = 0.7`

Then Japan gets reverse demand pressure:

```python
0.5 * 0.1 * 0.7 = 0.035
```

### `_pressure_concentration(...)`

This computes a Herfindahl-style concentration score:

```python
sum((pressure_share) ** 2)
```

Interpretation:

- near `1.0`
  - most pressure comes from one source
- lower values
  - pressure is spread across many sources

This is now used to weaken substitution when one dominant partner is responsible for most of the shock.

### `_apply_substitution_and_inventory(...)`

This is where incoming pressure is converted into actual shortage.

It does 4 things:

1. compute effective substitution
2. limit how much inventory is usable this step
3. calculate remaining shortage
4. split remaining shortage into immediate and deferred parts

#### Step A: substitution

Base substitution comes from the resilience profile.

Then the code weakens it using:

- total pressure
- pressure concentration

Formula:

```python
effective_substitution_rate =
    base_substitution_rate
    * (1 - concentration_penalty * concentration)
    * (1 - pressure ** exponent)
```

So substitution gets worse when:

- total pressure is large
- or pressure is concentrated in one source

#### Step B: inventory use

The code does **not** let the full inventory always be used.

Formula:

```python
usable_inventory_share =
    1 - inventory_stress_penalty * pressure ** inventory_stress_exponent
```

So for very large shocks:

- only part of the inventory is usable in that step

That makes the model more realistic than:

```python
inventory_used = min(all_inventory, shortage)
```

#### Step C: remaining shortage

After substitution and inventory:

```python
remaining_shortage = shortage_after_substitution - inventory_used
```

#### Step D: delay split

The shortage is split into:

- immediate shortage
- deferred shortage

using the country's `delay_share`.

So some shortages hit now, and some carry into the next step.

### `_apply_health_updates(...)`

This applies damage to countries.

Formula:

```python
total_damage =
    disruption * health_damage_scale
    + shortage * shortage_damage_scale
```

Then:

```python
country.apply_shock(total_damage)
```

So there are two sources of damage:

- current disruption
- immediate unresolved shortage

### `_rebuild_inventories(...)`

This rebuilds inventory after damage is applied.

Formula:

```python
rebuild_amount =
    inventory_rebuild_rate
    * current_health
    * (1 - max(disruption, pressure))
```

So inventory rebuild is larger when:

- the country is healthier
- current disruption is lower
- current pressure is lower

### `_compute_next_disruptions(...)`

This creates the disruption dictionary for the next time step.

For each country:

```python
lingering_disruption = current_disruption * persistence
next_impact = max(shortage, lingering_disruption)
```

If `next_impact >= threshold`, that country remains active.

So the simulation keeps going because each step produces the next step's `disruptions` map.

### `_resolve_profiles(...)`

This resolves:

- scalar profile value
- or per-country mapping

into per-country dictionaries once, before the main loop.

### `_build_step_snapshot(...)`

This packages one step into the replay format used by the dashboard.

Each step snapshot includes:

- `step`
- `shock_data`
- `health_data`
- `inventory_data`
- `pressure_data`
- `shortage_data`
- `deferred_shortage_data`

### `run_time_step_simulation(...)`

This is the main simulation function.

#### Setup

It:

1. resolves profiles
2. sanitizes initial shocks
3. creates the initial `StepState`

#### Loop

Each iteration:

1. compute trade pressure
2. combine with deferred shortage
3. apply substitution + inventory
4. damage countries
5. rebuild inventory
6. save a snapshot
7. compute next disruptions

#### Stop condition

The simulation stops when:

- no disruptions remain
- and no deferred shortage remains

or when the internal max step count is reached.

---

## 7. Example simulation trace

Suppose:

- initial shock: `{"JPN": 0.5}`
- Japan exports to Thailand
- Thailand has some inventory and some substitution ability

### Step 0

Current disruptions:

```python
{"JPN": 0.5}
```

Trade pressure:

```python
pressure["THA"] = 0.5 * supply_weight * trade_pressure_scale
```

If that becomes `0.10`, then Thailand resists it.

After substitution and inventory:

```python
shortage["THA"] = 0.03
deferred_shortage["THA"] = 0.01
```

Health update:

```python
damage = disruption * health_damage_scale + shortage * shortage_damage_scale
```

Japan loses health from its own disruption.
Thailand loses health from shortage.

Next disruptions:

```python
{"JPN": 0.1, "THA": 0.03}
```

### Step 1

Now both Japan and Thailand can affect others.

Japan still sends reduced pressure.
Thailand may now send some buyer-side or supplier-side pressure through its own edges.

That is how the process continues.

---

## 8. `dashboard.py`

File: [version_2/dashboard.py](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/dashboard.py)

This file is the browser UI layer.

### `_load_base_graph(args)`

This does the full data-loading startup:

1. `load_country_coordinates(...)`
2. `load_gdp_data(...)`
3. `load_trade_data(...)`
4. `validate_country_matches(...)`
5. `build_trade_graph(...)`

So the actual graph is built here when the app starts.

### `build_country_dropdown_options(...)`

This creates the country dropdown choices sorted by country name.

### `build_default_shock_lookup()` and `sync_shock_rows(...)`

These build the default country+shock table shown in the UI.

### `_run_simulation_from_controls(...)`

This is the bridge between the UI and the simulation.

It:

1. clones the base graph
2. resets all country health
3. reads selected countries and shock values from the dashboard controls
4. computes resilience profiles
5. calls `run_time_step_simulation(...)`
6. chooses visible countries
7. returns the simulation result bundle

Important point:

- the dashboard never mutates the original base graph directly
- it always works on a cloned graph for each run

### `_render_dashboard_figure(...)`

This converts saved simulation data into one Plotly figure for the current step.

If there is no simulation data yet, it shows a default empty figure.

### `run_dashboard(args)`

This creates the Dash app and layout.

The layout includes:

- starting country dropdown
- shock table
- threshold input
- visible country count
- visible edge count
- hide edges toggle
- create simulation button
- previous / play / next buttons
- step slider
- graph

It also creates:

- `dcc.Store` for saved simulation data
- `dcc.Store` for playback state
- `dcc.Interval` for playback ticking

Then it defines the callbacks:

- sync the shock table when selected countries change
- run a new simulation when the button is pressed
- update playback state
- render the current step figure

So `dashboard.py` is the control system for the app.

---

## 9. `visualization.py`

File: [version_2/visualization.py](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/visualization.py)

This file turns step snapshots into Plotly graphics.

### `_build_edge_trace(...)`

This draws edge lines between exporter and importer centroids.

Edges are only drawn if:

- both countries are visible
- and at least one endpoint is active in the current step

That avoids drawing the entire world network at once.

### `_build_country_trace(...)`

This creates the choropleth layer:

- each country's fill color is based on `health_data`

So this is the main world-map coloring layer.

### `_build_active_marker_trace(...)`

This puts circular markers on currently disrupted countries.

Marker size depends on:

- GDP size
- current impact size

So larger economies and larger disruptions create bigger markers.

### `create_step_figure(...)`

This builds one static figure for one chosen step.

It combines:

1. edges
2. choropleth
3. active markers

### `create_simulation_figure(...)`

This creates a full Plotly animated figure using frames.

The dashboard mostly uses `create_step_figure(...)` for manual playback instead of relying only on Plotly frame controls.

---

## 10. What the program stores at each step

Each step snapshot contains:

- `shock_data`
  - active disruptions this step
- `health_data`
  - country health values
- `inventory_data`
  - inventory after rebuilding
- `pressure_data`
  - combined pressure, including deferred shortage
- `shortage_data`
  - immediate shortage after substitution and inventory
- `deferred_shortage_data`
  - shortage carried to the next step

This is exactly what the map and playback controls visualize.

---

## 11. The most important formulas

### Supply-side pressure

```python
exporter_disruption * supply_weight * trade_pressure_scale
```

### Demand-side pressure

```python
importer_disruption * demand_weight * demand_pressure_scale
```

### Substitution

```python
base_substitution_rate
* (1 - concentration_penalty * concentration)
* (1 - pressure ** exponent)
```

### Usable inventory in one step

```python
inventory * (1 - inventory_stress_penalty * pressure ** inventory_stress_exponent)
```

### Damage

```python
disruption * health_damage_scale + shortage * shortage_damage_scale
```

### Persistence

```python
current_disruption * persistence
```

### Next step disruption

```python
max(shortage, lingering_disruption)
```

---

## 12. Shortest plain-English summary

The code builds a directed weighted trade graph from real GDP and bilateral trade data.

Each edge stores both:

- how much the importer depends on the exporter
- how much the exporter depends on the importer as a buyer

The simulation then runs in repeated steps:

1. disrupted countries create supply and demand pressure
2. countries try to resist that pressure using substitution and inventory
3. unresolved shortage damages country health
4. some shortage is delayed into the next step
5. some disruption persists
6. the next step begins

The dashboard saves all steps and shows them on a Plotly world map.

