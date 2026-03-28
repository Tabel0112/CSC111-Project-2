"""CSV parsing utilities for GDP, trade, and coordinate data."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from config import AGGREGATE_NAME_KEYWORDS
from utils import safe_float

CSV_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def clean_country_codes(code: str) -> Optional[str]:
    """Return a cleaned ISO-3 country code, or None if it is invalid.

    >>> clean_country_codes("can")
    'CAN'
    >>> clean_country_codes(" twn ")
    'TWN'
    >>> clean_country_codes("W00") is None
    True
    >>> clean_country_codes("US") is None
    True
    """
    cleaned = code.strip().upper()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned
    return None


def _normalize_header(header: str) -> str:
    """Return a simplified header name for matching."""
    return "".join(character for character in header.lower() if character.isalnum())


def _read_csv_rows(path: str) -> list[list[str]]:
    """Return all rows from a CSV file using a small encoding fallback list."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CSV file: {path}")

    last_error = None
    for encoding in CSV_ENCODINGS:
        try:
            with csv_path.open("r", encoding=encoding, newline="") as file:
                return list(csv.reader(file))
        except UnicodeDecodeError as exc:
            last_error = exc

    raise UnicodeError(f"Could not decode CSV file: {path}") from last_error


def _find_header_index(path: str, required_headers: set[str]) -> tuple[int, list[str]]:
    """Return the header row index and header cells for a CSV file."""
    for index, row in enumerate(_read_csv_rows(path)):
        normalized = {_normalize_header(cell) for cell in row}
        if required_headers.issubset(normalized):
            return index, row

    raise ValueError(f"Could not find a usable header row in {path}")


def _load_dict_rows_from_index(path: str, header_index: int) -> tuple[list[dict[str, str]], list[str]]:
    """Return CSV rows after skipping lines before <header_index>."""
    rows = []
    csv_rows = _read_csv_rows(path)
    header = csv_rows[header_index]

    for raw_row in csv_rows[header_index + 1:]:
        if not any(cell.strip() for cell in raw_row):
            continue

        aligned_row = raw_row[:len(header)]
        if len(aligned_row) < len(header):
            aligned_row.extend([""] * (len(header) - len(aligned_row)))

        rows.append(
            {
                key: value.strip()
                for key, value in zip(header, aligned_row)
            }
        )

    return rows, header


def _load_dict_rows(path: str, required_headers: set[str]) -> tuple[list[dict[str, str]], list[str]]:
    """Return rows from <path> after automatically locating the real header row."""
    header_index, _ = _find_header_index(path, required_headers)
    return _load_dict_rows_from_index(path, header_index)


def _find_column_name(headers: list[str], candidates: list[str]) -> Optional[str]:
    """Return the actual header name that matches one of the candidates."""
    normalized_to_actual = {
        _normalize_header(header): header
        for header in headers
    }

    for candidate in candidates:
        normalized = _normalize_header(candidate)
        if normalized in normalized_to_actual:
            return normalized_to_actual[normalized]

    return None


def _is_probable_country(name: str) -> bool:
    """Return whether a World Bank name looks like an individual country."""
    lowered = name.lower()
    return not any(keyword in lowered for keyword in AGGREGATE_NAME_KEYWORDS)


def _infer_gdp_metadata_path(gdp_path: str) -> Optional[Path]:
    """Return the matching World Bank country-metadata path when available."""
    csv_path = Path(gdp_path)
    if not csv_path.exists():
        return None

    direct_match = csv_path.with_name(f"Metadata_Country_{csv_path.name}")
    if direct_match.exists():
        return direct_match

    matches = sorted(csv_path.parent.glob("Metadata_Country*.csv"))
    if matches:
        return matches[0]

    return None


def _load_world_bank_country_codes(metadata_path: str) -> set[str]:
    """Return World Bank metadata codes that represent countries/economies, not aggregates."""
    rows, header = _load_dict_rows(metadata_path, {"countrycode", "region", "incomegroup"})
    code_column = _find_column_name(header, ["Country Code"])
    region_column = _find_column_name(header, ["Region"])
    income_group_column = _find_column_name(header, ["IncomeGroup", "Income Group"])
    assert code_column is not None and region_column is not None and income_group_column is not None

    valid_codes = set()
    for row in rows:
        code = clean_country_codes(row.get(code_column, ""))
        if code is None:
            continue

        # In World Bank metadata, aggregate groups have blank Region and IncomeGroup.
        if row.get(region_column, "").strip() or row.get(income_group_column, "").strip():
            valid_codes.add(code)

    return valid_codes


def _find_trade_header_index(path: str) -> int:
    """Return the most likely header row for a Comtrade-style CSV file."""
    reporter_candidates = {
        "reporteriso",
        "reportercode",
        "reporter",
        "reporterdesc",
    }
    partner_candidates = {
        "partneriso",
        "partnercode",
        "partner",
        "partnerdesc",
    }
    value_candidates = {
        "primaryvalue",
        "tradevalue",
        "tradevalueus",
        "fobvalue",
    }

    for index, row in enumerate(_read_csv_rows(path)):
        normalized = {_normalize_header(cell) for cell in row}
        has_reporter = any(candidate in normalized for candidate in reporter_candidates)
        has_partner = any(candidate in normalized for candidate in partner_candidates)
        has_value = any(candidate in normalized for candidate in value_candidates)

        if has_reporter and has_partner and has_value:
            return index

    raise ValueError(f"Could not find a usable Comtrade header row in {path}")


def load_gdp_data(path: str) -> dict[str, dict[str, object]]:
    """Load nominal GDP for 2023 from a World Bank CSV file."""
    required_headers = {"countryname", "countrycode"}
    rows, header = _load_dict_rows(path, required_headers)
    metadata_path = _infer_gdp_metadata_path(path)
    allowed_country_codes = (
        _load_world_bank_country_codes(str(metadata_path))
        if metadata_path is not None
        else None
    )

    year_column = None
    for column in header:
        normalized = _normalize_header(column)
        if normalized == "2023" or normalized.startswith("2023yr2023"):
            year_column = column
            break

    if year_column is None:
        raise ValueError("Could not find a 2023 GDP column in the GDP CSV.")

    country_name_column = _find_column_name(header, ["Country Name"])
    country_code_column = _find_column_name(header, ["Country Code"])
    assert country_name_column is not None and country_code_column is not None

    gdp_data = {}
    for row in rows:
        code = clean_country_codes(row[country_code_column])
        name = row[country_name_column]
        gdp_value = safe_float(row.get(year_column, ""), default=0.0)

        if code is None or gdp_value <= 0:
            continue

        if allowed_country_codes is not None:
            if code not in allowed_country_codes:
                continue
        elif not _is_probable_country(name):
            continue

        gdp_data[code] = {"name": name, "gdp": gdp_value}

    return gdp_data


def load_trade_data(path: str) -> list[dict[str, object]]:
    """Load export trade rows from a Comtrade CSV file."""
    header_index = _find_trade_header_index(path)
    rows, headers = _load_dict_rows_from_index(path, header_index)

    flow_column = _find_column_name(headers, ["flowDesc", "flow", "trade flow", "flow"])
    reporter_code_column = _find_column_name(
        headers,
        ["reporterISO", "reporter_iso", "Reporter ISO", "reportercode", "reporterCode"],
    )
    reporter_name_column = _find_column_name(headers, ["reporterDesc", "reporter", "Reporter"])
    partner_code_column = _find_column_name(
        headers,
        ["partnerISO", "partner_iso", "Partner ISO", "partnercode", "partnerCode"],
    )
    partner_name_column = _find_column_name(headers, ["partnerDesc", "partner", "Partner"])
    trade_value_column = _find_column_name(
        headers,
        [
            "primaryValue",
            "primary_value",
            "tradeValue",
            "trade value",
            "Trade Value (US$)",
            "fobvalue",
        ],
    )

    if reporter_code_column is None or partner_code_column is None or trade_value_column is None:
        raise ValueError(
            "Could not identify exporter, importer, and trade value columns in the trade CSV."
        )

    trade_rows = []
    saw_world_total_row = False
    saw_non_world_partner = False

    for row in rows:
        if flow_column is not None:
            flow_value = row.get(flow_column, "").lower()
            if "export" not in flow_value:
                continue

        raw_partner_code = row.get(partner_code_column, "").strip().upper()
        raw_partner_name = row.get(partner_name_column, "").strip().lower()
        partner_is_world = raw_partner_code == "W00" or raw_partner_name == "world"
        if partner_is_world:
            saw_world_total_row = True
        elif raw_partner_code:
            saw_non_world_partner = True

        exporter_code = clean_country_codes(row.get(reporter_code_column, ""))
        importer_code = clean_country_codes(row.get(partner_code_column, ""))
        exporter_name = row.get(reporter_name_column, exporter_code or "Unknown")
        importer_name = row.get(partner_name_column, importer_code or "Unknown")
        trade_value = safe_float(row.get(trade_value_column, ""), default=0.0)

        if (
            exporter_code is None
            or importer_code is None
            or partner_is_world
            or trade_value <= 0
        ):
            continue

        trade_rows.append(
            {
                "exporter_code": exporter_code,
                "exporter_name": exporter_name,
                "importer_code": importer_code,
                "importer_name": importer_name,
                "trade_value": trade_value,
            }
        )

    if not trade_rows:
        if saw_world_total_row and not saw_non_world_partner:
            raise ValueError(
                "Trade CSV contains only world-total export rows. "
                "Download bilateral partner data instead of a World-only export."
            )

        raise ValueError("Trade CSV does not contain any usable bilateral export rows.")

    return trade_rows


def load_country_coordinates(path: str) -> dict[str, tuple[float, float]]:
    """Load country coordinates from a simple CSV file with code, lat, and lon columns."""
    csv_path = Path(path)
    if not csv_path.exists():
        return {}

    try:
        header_index, header = _find_header_index(
            path,
            {"code", "lat", "lon"},
        )
    except ValueError:
        header_index, header = _find_header_index(
            path,
            {"alpha3code", "latitudeaverage", "longitudeaverage"},
        )

    rows, header = _load_dict_rows_from_index(path, header_index)

    code_column = _find_column_name(
        header,
        ["code", "country_code", "iso3", "Alpha-3 code"],
    )
    lat_column = _find_column_name(
        header,
        ["lat", "latitude", "Latitude (average)"],
    )
    lon_column = _find_column_name(
        header,
        ["lon", "longitude", "lng", "Longitude (average)"],
    )
    assert code_column is not None and lat_column is not None and lon_column is not None

    coordinates = {}
    for row in rows:
        code = clean_country_codes(row.get(code_column, ""))
        if code is None:
            continue

        coordinates[code] = (
            safe_float(row.get(lat_column, ""), default=0.0),
            safe_float(row.get(lon_column, ""), default=0.0),
        )

    return coordinates


def validate_country_matches(
    gdp_data: dict[str, dict[str, object]],
    trade_data: list[dict[str, object]],
) -> dict[str, set[str]]:
    """Return a simple summary of code overlap between GDP and trade data."""
    gdp_codes = set(gdp_data)
    trade_exporters = {str(row["exporter_code"]) for row in trade_data}
    trade_importers = {str(row["importer_code"]) for row in trade_data}

    return {
        "gdp_only": gdp_codes - trade_exporters - trade_importers,
        "trade_only": (trade_exporters | trade_importers) - gdp_codes,
        "shared": gdp_codes & (trade_exporters | trade_importers),
    }


if __name__ == "__main__":
    import doctest
    import python_ta
    from pyta_config import PYTA_CONFIG

    doctest.testmod()
    python_ta.check_all(config=PYTA_CONFIG)
