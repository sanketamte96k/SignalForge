from src.universe.models import Instrument
from src.universe.nifty50 import load_nifty50
from src.universe.sector import Sector
from src.universe.validation import ValidationStatus
from src.universe.watchlist import Watchlist


class UniverseManager:
    """Manage the SignalForge instrument universe."""

    def __init__(
        self,
        instruments: tuple[Instrument, ...] | None = None,
        sectors: tuple[Sector, ...] | None = None,
        watchlists: tuple[Watchlist, ...] | None = None,
    ) -> None:
        loaded_instruments = (
            tuple(load_nifty50())
            if instruments is None
            else tuple(instruments)
        )

        if not loaded_instruments:
            raise ValueError(
                "universe must contain at least one instrument"
            )

        instrument_symbols = [
            instrument.symbol
            for instrument in loaded_instruments
        ]

        if len(instrument_symbols) != len(set(instrument_symbols)):
            raise ValueError(
                "universe contains duplicate symbols"
            )

        self._instruments = list(loaded_instruments)

        self._instrument_by_symbol = {
            instrument.symbol: instrument
            for instrument in self._instruments
        }

        self._sectors: list[Sector] = []
        self._watchlists: list[Watchlist] = []

        if sectors is not None:
            for sector in sectors:
                self._validate_unique_sector_name(
                    sector.name
                )

                for symbol in sector.symbols:
                    if symbol not in self._instrument_by_symbol:
                        raise ValueError(
                            "sector contains unknown instrument"
                        )

                self._sectors.append(sector)

        if watchlists is not None:
            for watchlist in watchlists:
                self._validate_unique_watchlist_name(
                    watchlist.name
                )

                for symbol in watchlist.symbols:
                    if symbol not in self._instrument_by_symbol:
                        raise ValueError(
                            "watchlist contains unknown instrument"
                        )

                self._watchlists.append(watchlist)

    # ------------------------------------------------------------------
    # Instrument management
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of instruments in the universe."""
        return len(self._instruments)

    def all_instruments(self) -> tuple[Instrument, ...]:
        """Return all instruments in universe order."""
        return tuple(self._instruments)

    def symbols(self) -> tuple[str, ...]:
        """Return all instrument symbols in universe order."""
        return tuple(
            instrument.symbol
            for instrument in self._instruments
        )

    def get_instrument(self, symbol: str) -> Instrument:
        """Return an instrument by symbol."""
        normalized_symbol = self._normalize_symbol(symbol)

        try:
            return self._instrument_by_symbol[
                normalized_symbol
            ]
        except KeyError as exc:
            raise KeyError(
                f"instrument not found in universe: "
                f"{normalized_symbol}"
            ) from exc

    def contains(self, symbol: str) -> bool:
        """Return whether a symbol exists in the universe."""
        normalized_symbol = self._normalize_symbol(symbol)
        return normalized_symbol in self._instrument_by_symbol

    def search_instruments(
        self,
        query: str,
    ) -> tuple[Instrument, ...]:
        """Search instruments by symbol or company name."""
        normalized_query = " ".join(
            query.strip().casefold().split()
        )

        if not normalized_query:
            raise ValueError(
                "search query must not be empty"
            )

        matches: list[Instrument] = []

        for instrument in self._instruments:
            normalized_symbol = instrument.symbol.casefold()
            normalized_name = instrument.name.casefold()

            if (
                normalized_query in normalized_symbol
                or normalized_query in normalized_name
            ):
                matches.append(instrument)

        return tuple(matches)

    # ------------------------------------------------------------------
    # Validation status management
    # ------------------------------------------------------------------

    def get_validation_status(
        self,
        symbol: str,
    ) -> ValidationStatus:
        """Return the validation status of an instrument."""
        return self.get_instrument(symbol).validation_status

    def set_validation_status(
        self,
        symbol: str,
        status: ValidationStatus | str,
    ) -> Instrument:
        """
        Update an instrument's validation status.

        Instrument objects remain immutable. The manager replaces the
        instrument with a new immutable instance while preserving all
        other instrument metadata.
        """
        normalized_symbol = self._normalize_symbol(symbol)
        instrument = self.get_instrument(normalized_symbol)

        try:
            normalized_status = (
                status
                if isinstance(status, ValidationStatus)
                else ValidationStatus(status)
            )
        except ValueError as exc:
            raise ValueError(
                "status must be a valid ValidationStatus"
            ) from exc

        updated_instrument = Instrument(
            symbol=instrument.symbol,
            name=instrument.name,
            exchange=instrument.exchange,
            instrument_type=instrument.instrument_type,
            validation_status=normalized_status,
        )

        for index, existing in enumerate(self._instruments):
            if existing.symbol == normalized_symbol:
                self._instruments[index] = updated_instrument
                break

        self._instrument_by_symbol[
            normalized_symbol
        ] = updated_instrument

        return updated_instrument

    def is_validated(self, symbol: str) -> bool:
        """Return whether an instrument is validated for signals."""
        return (
            self.get_validation_status(symbol)
            == ValidationStatus.VALIDATED
        )

    def is_signal_eligible(self, symbol: str) -> bool:
        """
        Return whether an instrument is allowed to reach the
        stock signal engine.

        Only VALIDATED instruments are eligible.
        TESTING and FAILED instruments are always blocked.
        """
        return self.is_validated(symbol)

    def signal_eligible_symbols(self) -> tuple[str, ...]:
        """
        Return all symbols currently eligible for signal generation.

        Symbols remain in universe order.
        """
        return tuple(
            instrument.symbol
            for instrument in self._instruments
            if instrument.validation_status
            == ValidationStatus.VALIDATED
        )

    def signal_eligible_instruments(
        self,
    ) -> tuple[Instrument, ...]:
        """
        Return all instruments currently eligible for signal generation.

        Instruments remain in universe order.
        """
        return tuple(
            instrument
            for instrument in self._instruments
            if instrument.validation_status
            == ValidationStatus.VALIDATED
        )

    # ------------------------------------------------------------------
    # Sector management
    # ------------------------------------------------------------------

    def all_sectors(self) -> tuple[Sector, ...]:
        """Return all sectors."""
        return tuple(self._sectors)

    def create_sector(
        self,
        name: str,
        description: str = "",
    ) -> Sector:
        """Create and register a new sector."""
        self._validate_unique_sector_name(name)

        sector = Sector(
            name=name,
            description=description,
        )

        self._sectors.append(sector)
        return sector

    def get_sector(self, name: str) -> Sector:
        """Return a sector by name."""
        normalized_name = self._normalize_name(
            name,
            "sector name",
        )

        for sector in self._sectors:
            if (
                sector.name.casefold()
                == normalized_name.casefold()
            ):
                return sector

        raise KeyError(
            f"sector not found: {name}"
        )

    def contains_sector(self, name: str) -> bool:
        """Return whether a sector exists."""
        normalized_name = self._normalize_name(
            name,
            "sector name",
        )

        return any(
            sector.name.casefold()
            == normalized_name.casefold()
            for sector in self._sectors
        )

    def add_stock_to_sector(
        self,
        sector_name: str,
        symbol: str,
    ) -> Sector:
        """Add a stock to a sector."""
        normalized_symbol = self._normalize_symbol(symbol)

        if normalized_symbol not in self._instrument_by_symbol:
            raise KeyError(
                "instrument not found in universe: "
                f"{normalized_symbol}"
            )

        sector = self.get_sector(sector_name)

        if normalized_symbol in sector.symbols:
            raise ValueError(
                "stock already exists in sector: "
                f"{normalized_symbol}"
            )

        updated_sector = Sector(
            name=sector.name,
            description=sector.description,
            symbols=sector.symbols + (normalized_symbol,),
        )

        self._replace_sector(updated_sector)

        return updated_sector

    def remove_stock_from_sector(
        self,
        sector_name: str,
        symbol: str,
    ) -> Sector:
        """Remove a stock from a sector."""
        normalized_symbol = self._normalize_symbol(symbol)
        sector = self.get_sector(sector_name)

        if normalized_symbol not in sector.symbols:
            raise KeyError(
                "stock not found in sector: "
                f"{normalized_symbol}"
            )

        updated_symbols = tuple(
            existing
            for existing in sector.symbols
            if existing != normalized_symbol
        )

        updated_sector = Sector(
            name=sector.name,
            description=sector.description,
            symbols=updated_symbols,
        )

        self._replace_sector(updated_sector)

        return updated_sector

    def sector_symbols(
        self,
        sector_name: str,
    ) -> tuple[str, ...]:
        """Return the symbols belonging to a sector."""
        return self.get_sector(sector_name).symbols

    # ------------------------------------------------------------------
    # Watchlist management
    # ------------------------------------------------------------------

    def all_watchlists(self) -> tuple[Watchlist, ...]:
        """Return all watchlists."""
        return tuple(self._watchlists)

    def create_watchlist(
        self,
        name: str,
        description: str = "",
    ) -> Watchlist:
        """Create and register a new watchlist."""
        self._validate_unique_watchlist_name(name)

        watchlist = Watchlist(
            name=name,
            description=description,
        )

        self._watchlists.append(watchlist)
        return watchlist

    def get_watchlist(self, name: str) -> Watchlist:
        """Return a watchlist by name."""
        normalized_name = self._normalize_name(
            name,
            "watchlist name",
        )

        for watchlist in self._watchlists:
            if (
                watchlist.name.casefold()
                == normalized_name.casefold()
            ):
                return watchlist

        raise KeyError(
            f"watchlist not found: {name}"
        )

    def contains_watchlist(self, name: str) -> bool:
        """Return whether a watchlist exists."""
        normalized_name = self._normalize_name(
            name,
            "watchlist name",
        )

        return any(
            watchlist.name.casefold()
            == normalized_name.casefold()
            for watchlist in self._watchlists
        )

    def add_stock_to_watchlist(
        self,
        watchlist_name: str,
        symbol: str,
    ) -> Watchlist:
        """Add a stock to a watchlist."""
        normalized_symbol = self._normalize_symbol(symbol)

        if normalized_symbol not in self._instrument_by_symbol:
            raise KeyError(
                "instrument not found in universe: "
                f"{normalized_symbol}"
            )

        watchlist = self.get_watchlist(watchlist_name)

        if normalized_symbol in watchlist.symbols:
            raise ValueError(
                "stock already exists in watchlist: "
                f"{normalized_symbol}"
            )

        updated_watchlist = Watchlist(
            name=watchlist.name,
            description=watchlist.description,
            symbols=watchlist.symbols + (normalized_symbol,),
        )

        self._replace_watchlist(updated_watchlist)

        return updated_watchlist

    def remove_stock_from_watchlist(
        self,
        watchlist_name: str,
        symbol: str,
    ) -> Watchlist:
        """Remove a stock from a watchlist."""
        normalized_symbol = self._normalize_symbol(symbol)
        watchlist = self.get_watchlist(watchlist_name)

        if normalized_symbol not in watchlist.symbols:
            raise KeyError(
                "stock not found in watchlist: "
                f"{normalized_symbol}"
            )

        updated_symbols = tuple(
            existing
            for existing in watchlist.symbols
            if existing != normalized_symbol
        )

        updated_watchlist = Watchlist(
            name=watchlist.name,
            description=watchlist.description,
            symbols=updated_symbols,
        )

        self._replace_watchlist(updated_watchlist)

        return updated_watchlist

    def watchlist_symbols(
        self,
        watchlist_name: str,
    ) -> tuple[str, ...]:
        """Return the symbols belonging to a watchlist."""
        return self.get_watchlist(watchlist_name).symbols

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "symbol must not be empty"
            )

        return normalized

    @staticmethod
    def _normalize_name(
        name: str,
        field_name: str,
    ) -> str:
        normalized = " ".join(
            name.strip().split()
        )

        if not normalized:
            raise ValueError(
                f"{field_name} must not be empty"
            )

        return normalized

    def _validate_unique_sector_name(
        self,
        name: str,
    ) -> None:
        normalized_name = self._normalize_name(
            name,
            "sector name",
        )

        if any(
            sector.name.casefold()
            == normalized_name.casefold()
            for sector in self._sectors
        ):
            raise ValueError(
                f"sector already exists: {name}"
            )

    def _validate_unique_watchlist_name(
        self,
        name: str,
    ) -> None:
        normalized_name = self._normalize_name(
            name,
            "watchlist name",
        )

        if any(
            watchlist.name.casefold()
            == normalized_name.casefold()
            for watchlist in self._watchlists
        ):
            raise ValueError(
                f"watchlist already exists: {name}"
            )

    def _replace_sector(
        self,
        updated_sector: Sector,
    ) -> None:
        for index, sector in enumerate(self._sectors):
            if (
                sector.name.casefold()
                == updated_sector.name.casefold()
            ):
                self._sectors[index] = updated_sector
                return

        raise KeyError(
            f"sector not found: {updated_sector.name}"
        )

    def _replace_watchlist(
        self,
        updated_watchlist: Watchlist,
    ) -> None:
        for index, watchlist in enumerate(self._watchlists):
            if (
                watchlist.name.casefold()
                == updated_watchlist.name.casefold()
            ):
                self._watchlists[index] = updated_watchlist
                return

        raise KeyError(
            f"watchlist not found: {updated_watchlist.name}"
        )
