"""Tests for CSV parsing against realistic edge cases."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from data_parser import load_country_coordinates, load_gdp_data, load_trade_data


class TestDataParser(unittest.TestCase):
    """Tests for GDP and trade CSV parsing."""

    def write_bytes(self, filename: str, content: bytes) -> str:
        """Write bytes into a temporary file and return its path."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)

        path = Path(directory.name) / filename
        path.write_bytes(content)
        return str(path)

    def test_load_gdp_data_skips_metadata_and_aggregates(self) -> None:
        """The GDP parser should find the real header row and keep countries only."""
        path = self.write_bytes(
            "gdp.csv",
            (
                '"Data Source","World Development Indicators",\n'
                '"Last Updated Date","2026-02-24",\n'
                "\n"
                '"Country Name","Country Code","Indicator Name","Indicator Code","2022","2023"\n'
                '"Albania","ALB","GDP (current US$)","NY.GDP.MKTP.CD","189","200"\n'
                '"Early-demographic dividend","EAR","GDP (current US$)","NY.GDP.MKTP.CD","1000","1100"\n'
                '"No GDP","NGP","GDP (current US$)","NY.GDP.MKTP.CD","100",""\n'
            ).encode("utf-8"),
        )
        metadata_path = Path(path).with_name("Metadata_Country_gdp.csv")
        metadata_path.write_text(
            (
                '"Country Code","Region","IncomeGroup","SpecialNotes","TableName"\n'
                '"ALB","Europe & Central Asia","Upper middle income","","Albania"\n'
                '"EAR","","","Aggregate group","Early-demographic dividend"\n'
                '"NGP","Europe & Central Asia","Upper middle income","","No GDP"\n'
            ),
            encoding="utf-8",
        )

        gdp_data = load_gdp_data(path)

        self.assertEqual(gdp_data, {"ALB": {"name": "Albania", "gdp": 200.0}})

    def test_load_trade_data_handles_latin1_and_extra_columns(self) -> None:
        """The trade parser should decode Latin-1 and ignore trailing blank columns."""
        path = self.write_bytes(
            "trade.csv",
            (
                "reporterISO,reporterDesc,flowDesc,partnerISO,partnerDesc,primaryValue\n"
                "CIV,C\xf4te d'Ivoire,Export,FRA,France,123,\n"
                "ALB,Albania,Import,ITA,Italy,999,\n"
            ).encode("cp1252"),
        )

        trade_data = load_trade_data(path)

        self.assertEqual(
            trade_data,
            [
                {
                    "exporter_code": "CIV",
                    "exporter_name": "C\xf4te d'Ivoire".encode("cp1252").decode("cp1252"),
                    "importer_code": "FRA",
                    "importer_name": "France",
                    "trade_value": 123.0,
                }
            ],
        )

    def test_load_trade_data_rejects_world_totals_only(self) -> None:
        """The trade parser should reject a World-only export extract."""
        path = self.write_bytes(
            "world_only_trade.csv",
            (
                "reporterISO,reporterDesc,flowDesc,partnerISO,partnerDesc,primaryValue\n"
                "ALB,Albania,Export,W00,World,123,\n"
            ).encode("cp1252"),
        )

        with self.assertRaisesRegex(ValueError, "world-total export rows"):
            load_trade_data(path)

    def test_load_country_coordinates_supports_alpha3_headers(self) -> None:
        """The coordinate parser should accept common country-coordinate headers."""
        path = self.write_bytes(
            "country-coord.csv",
            (
                "Country,Alpha-2 code,Alpha-3 code,Numeric code,Latitude (average),Longitude (average)\n"
                "Canada,CA,CAN,124,60.0,-95.0\n"
                "United States,US,USA,840,38.0,-97.0\n"
            ).encode("utf-8"),
        )

        coordinates = load_country_coordinates(path)

        self.assertEqual(
            coordinates,
            {
                "CAN": (60.0, -95.0),
                "USA": (38.0, -97.0),
            },
        )


if __name__ == "__main__":
    unittest.main()
