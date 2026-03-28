# Macroeconomic Shock Simulator

This project models global trade dependencies as a directed weighted graph and simulates how an economic shock spreads over repeated time steps.

Countries are graph nodes. Directed edges point from exporter to importer. Each edge weight is:

`weight = trade_value / importer_total_imports`

This project uses a repeated time-step model rather than pure BFS waves. Each step combines:

- current exporter disruption
- import-shortage spillovers
- nonlinear supplier substitution
- inventory buffering
- delayed shortage carryover

The simulation saves every step and replays the result with Plotly.

## File Structure

- `main.py`: Runs the full program.
- `country_node.py`: Defines the `CountryNode` class.
- `data_parser.py`: Loads GDP, trade, and coordinate CSV files.
- `graph_builder.py`: Builds and filters the dictionary-based graph.
- `runtime_options.py`: Stores small parsing helpers used by the dashboard.
- `simulation.py`: Runs the repeated time-step disruption simulation.
- `visualization.py`: Creates the Plotly replay visualization.
- `config.py`: Stores constants and default file paths.
- `utils.py`: Stores small helper functions.
- `tests/`: Basic unit tests.
- `data/`: Expected location for GDP, trade, and coordinate CSV files.
- `CODE_WALKTHROUGH.md`: Detailed explanation of how the full code path works.

## Setup

1. Install Python 3.11 or later.
2. Install the required package:

```bash
pip install -r requirements.txt
```

## Running With Real Data

Place World Bank GDP, Comtrade trade, and optional coordinate files in the `data/` folder. The defaults auto-detect the newest matching files there, but these filenames also work:

- `data/world_bank_gdp.csv`
- `data/comtrade_trade.csv`
- `data/country_coordinates.csv` (optional but recommended)

Then run:

```bash
python main.py
```

This now opens the browser dashboard by default.

If port `8050` is already in use, the dashboard now automatically moves to the next free port.
You can also choose a port yourself:

```bash
python main.py --port 8060
```

Useful optional arguments:

- `--initial-countries "United States; China; Germany; Japan; India"`
- `--port 8050`
- `--hide-edges`

## Data Expectations

### GDP CSV

The parser is designed for World Bank style GDP exports. It automatically looks for the real header row, then searches for:

- `Country Name`
- `Country Code`
- a `2023` GDP column

It skips rows with missing GDP, invalid ISO-3 codes, and World Bank aggregate groups by checking the metadata country file when available.

### Trade CSV

The parser is designed for Comtrade-style CSV files. It tries to identify:

- exporter code column
- importer code column
- trade value column
- export flow column if present

The parser keeps only:

- export rows
- positive trade values
- valid ISO-3 country codes

It also drops rows where the importer is `World`.

### Coordinates CSV

If you provide a coordinate CSV, it should have simple columns such as:

- `code`
- `lat`
- `lon`

If coordinates are missing, the real-data graph still loads, but the geographic visualization will collapse onto default points.

## Testing

Run the basic tests with:

```bash
python -m unittest discover -s tests
```

## Understanding The Code

For a detailed explanation of how the data is loaded, how resilience profiles are computed, how each simulation step works, and how the dashboard renders saved states, read:

- `CODE_WALKTHROUGH.md`

## Current Limitations

- The simulation is still a simplified macro trade model, not a calibrated forecasting system.
- Trade dependence is approximated with importer trade-share weights, plus inferred resilience proxies rather than direct inventory data.
- Sector-level production is not modeled separately yet.
- The default visualization uses a 2D geographic projection rather than a more advanced globe.
- Edge filtering is applied after graph construction for readability.

## Future Extensions

- Add sector-level dynamics on top of the time-step model.
- Support richer coordinate datasets and cleaner map styling.
- Calibrate substitution and inventory rates with external literature or case studies.
- Export wave history to JSON for external analysis.
