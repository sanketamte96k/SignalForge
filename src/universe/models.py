from dataclasses import dataclass

from src.universe.validation import ValidationStatus


@dataclass(frozen=True)
class Instrument:
    """A tradeable market instrument."""

    symbol: str
    name: str
    exchange: str = "NSE"
    instrument_type: str = "EQUITY"
    validation_status: ValidationStatus = ValidationStatus.TESTING

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")

        if not self.name.strip():
            raise ValueError("name must not be empty")

        if not self.exchange.strip():
            raise ValueError("exchange must not be empty")

        if not self.instrument_type.strip():
            raise ValueError("instrument_type must not be empty")

        if not isinstance(self.validation_status, ValidationStatus):
            try:
                status = ValidationStatus(self.validation_status)
            except ValueError as exc:
                raise ValueError(
                    "validation_status must be a valid ValidationStatus"
                ) from exc

            object.__setattr__(
                self,
                "validation_status",
                status,
            )

        object.__setattr__(
            self,
            "symbol",
            self.symbol.strip().upper(),
        )

        object.__setattr__(
            self,
            "name",
            self.name.strip(),
        )

        object.__setattr__(
            self,
            "exchange",
            self.exchange.strip().upper(),
        )

        object.__setattr__(
            self,
            "instrument_type",
            self.instrument_type.strip().upper(),
        )
