# Macroeconomic Shock Simulator

This project models global trade dependencies as a directed weighted graph and simulates how an economic shock spreads wave by wave through that graph.

Countries are graph nodes. Directed edges point from exporter to importer. Each edge weight is:

`weight = trade_value / importer_gdp`

The simulator uses a normal BFS-style wave system. It processes one full wave at a time, combines all shocks that arrive at the same country in the same wave, applies multiplicative health damage, saves every wave, and then replays the result with Plotly.

## File Structure

- `main.py`: Runs the full program.
- `country_node.py`: Defines the `CountryNode` class.
- `country_input.py`: Resolves typed country names and typo suggestions.
- `data_parser.py`: Loads GDP, trade, and coordinate CSV files.
- `graph_builder.py`: Builds and filters the dictionary-based graph.
- `runtime_options.py`: Handles interactive prompts and runtime shock settings.
- `simulation.py`: Runs the BFS wave-by-wave shock simulation.
- `visualization.py`: Creates the Plotly replay visualization.
- `config.py`: Stores constants and default file paths.
- `utils.py`: Stores small helper functions.
- `tests/`: Basic unit tests.
- `data/`: Expected location for GDP, trade, and coordinate CSV files.

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

Useful optional arguments:

- `--initial-countries "United States; China; Germany; Japan; India"`
- `--initial-shock 0.2`
- `--initial-shocks "0.35,0.3,0.25,0.2,0.18"`
- `--threshold 0.002`
- `--top-n 170`
- `--top-k 40`
- `--visible-by trade`
- `--no-prompt`
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

## Current Limitations

- The simulation is still a simplified trade-network model, not a calibrated real-world forecasting model.
- Trade dependence is approximated with `trade_value / importer_gdp`, capped for stability.
- The default visualization uses a 2D geographic projection rather than a more advanced globe.
- Edge filtering is applied after graph construction for readability.

## Future Extensions

- Add shocks while the simulation is already running.
- Support richer coordinate datasets and cleaner map styling.
- Add sector-level or time-step based dynamics for more realism.
- Export wave history to JSON for external analysis.
