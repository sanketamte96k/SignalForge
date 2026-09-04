from dataclasses import dataclass


@dataclass(frozen=True)
class Watchlist:
    """A user-defined watchlist of instruments."""

    name: str
    description: str = ""
    symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized_name = self.name.strip()

        if not normalized_name:
            raise ValueError("watchlist name must not be empty")

        normalized_description = self.description.strip()

        normalized_symbols: list[str] = []

        for symbol in self.symbols:
            normalized_symbol = symbol.strip().upper()

            if not normalized_symbol:
                raise ValueError("watchlist symbol must not be empty")

            if normalized_symbol in normalized_symbols:
                raise ValueError(
                    f"watchlist contains duplicate symbol: {normalized_symbol}"
                )

            normalized_symbols.append(normalized_symbol)

        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(
            self,
            "description",
            normalized_description,
        )
        object.__setattr__(
            self,
            "symbols",
            tuple(normalized_symbols),
        )
