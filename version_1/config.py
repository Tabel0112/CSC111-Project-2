"""Configuration values for the macroeconomic shock simulator."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

def _pick_default_data_file(expected_name: str, glob_pattern: str) -> Path:
    """Return an existing data file when possible, otherwise the expected path."""
    expected_path = DATA_DIR / expected_name
    if expected_path.exists():
        return expected_path

    matches = sorted(
        DATA_DIR.glob(glob_pattern),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    if matches:
        return matches[0]

    return expected_path


DEFAULT_GDP_FILE = _pick_default_data_file(
    "world_bank_gdp.csv",
    "API_NY.GDP.MKTP.CD_DS2_en_csv_v2_*.csv",
)
DEFAULT_TRADE_FILE = _pick_default_data_file("comtrade_trade.csv", "TradeData_*.csv")
DEFAULT_COORDINATE_FILE = _pick_default_data_file(
    "country_coordinates.csv",
    "country*coord*.csv",
)

DEFAULT_THRESHOLD = 0.002
MIN_HEALTH_CUTOFF = 0.001
DEFAULT_INITIAL_SHOCK = 0.2
DEFAULT_INITIAL_COUNTRIES = "United States; China; Germany; Japan; India"
DEFAULT_INITIAL_SHOCKS = "0.35,0.3,0.25,0.2,0.18"
DEFAULT_TOP_N_COUNTRIES = 170
DEFAULT_TOP_K_EDGES = 40
DEFAULT_MAX_WAVES = 12
MAX_EDGE_WEIGHT = 0.5
SHOCK_PERSISTENCE = 0.2
DEFAULT_VISIBLE_BY = "trade"

SHOW_EDGES = True
REPLAY_ENABLED = True

# Common names that usually identify aggregates rather than individual countries.
AGGREGATE_NAME_KEYWORDS = {
    "africa",
    "america",
    "arab",
    "asia",
    "caribbean",
    "central europe",
    "east asia",
    "euro area",
    "europe",
    "high income",
    "income",
    "latin america",
    "middle east",
    "north america",
    "oecd",
    "pacific",
    "small states",
    "south asia",
    "sub-saharan",
    "union",
    "world",
}
