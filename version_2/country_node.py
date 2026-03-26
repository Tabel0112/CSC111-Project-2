"""Country node model for the trade graph."""

from __future__ import annotations

from config import MIN_HEALTH_CUTOFF


class CountryNode:
    """A country in the macroeconomic trade graph.
    Instance Attributes:
    - code: Alpha-3 code for each country
    - name: Full name of each country
    - total_gdp: Nominal GDP of each country
    - lat: Latitude coordinate of each country
    - lon: Longitude coordinate of each country
    - total_imports: Sum of all imports for each country
    - total_exports: Sum of all exports for each country
    - current_health: Percentage representing current financial status of the country
    - trading_partners: Dictionary representing each neighbors and weighted edge
    """
    
    code: str
    name: str
    total_gdp: float
    lat: float
    lon: float
    total_imports: float
    total_exports: float
    current_health: float
    trading_partners: dict[CountryNode, float]

    def __init__(
        self,
        code: str,
        name: str,
        total_gdp: float,
        lat: float = 0.0,
        lon: float = 0.0,
        total_imports: float = 0.0,
        total_exports: float = 0.0,
    ) -> None:
        """Initialize this country node."""
        self.code = code
        self.name = name
        self.total_gdp = total_gdp
        self.lat = lat
        self.lon = lon
        self.total_imports = total_imports
        self.total_exports = total_exports
        self.current_health = 1.0
        self.trading_partners = {}

    def add_trading_partner(self, partner: CountryNode, weight: float) -> None:
        """Add or update a directed edge to <partner>."""
        if weight > 0:
            self.trading_partners[partner] = weight

    def apply_shock(self, shock: float, cutoff: float = MIN_HEALTH_CUTOFF) -> float:
        """Apply a multiplicative shock and return the updated health."""
        bounded_shock = max(0.0, min(shock, 1.0))
        self.current_health = self.current_health * (1.0 - bounded_shock)

        if self.current_health < cutoff:
            self.current_health = 0.0

        return self.current_health

    def reset_health(self) -> None:
        """Reset this country's health to an undamaged state."""
        self.current_health = 1.0

    def __hash__(self) -> int:
        """Return a hash based on the ISO-3 code."""
        return hash(self.code)

    def __eq__(self, other: object) -> bool:
        """Return whether <other> is the same country code."""
        return isinstance(other, CountryNode) and self.code == other.code

    def __repr__(self) -> str:
        """Return a helpful string representation."""
        return (
            f"CountryNode(code={self.code!r}, name={self.name!r}, "
            f"gdp={self.total_gdp:.2f}, imports={self.total_imports:.2f}, "
            f"exports={self.total_exports:.2f}, health={self.current_health:.3f})"
        )
