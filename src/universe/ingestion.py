"""SignalForge Auditable Stock Universe Constituent Ingestion Engine.

Provides reproducible, verifiable constituent importing for NIFTY 50 and NIFTY Next 50:
- Explicit provenance recording (source name, URL, retrieval timestamp, as-of date, sha256).
- Strict separation between official source membership and local registered membership.
- Symbol normalization and conflict detection.
- Dry-run mode by default, leaving persistent stores completely untouched.
- Protection against silent deletion of custom stocks.
- Explicit confirmation required before any constituent removals are executed.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
from io import StringIO
from pathlib import Path
from typing import Any, Optional

from src.universe.registry import (
    StockRecord,
    StockUniverseRegistry,
    UniverseCategory,
)


@dataclass
class SourceProvenance:
    """Provenance audit metadata for an external constituent data source."""

    source_name: str
    source_url: str
    retrieval_timestamp: datetime
    as_of_date: str
    constituent_count: int
    sha256: str
    local_file: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_url": self.source_url,
            "local_file": self.local_file,
            "retrieval_timestamp": self.retrieval_timestamp.isoformat(),
            "as_of_date": self.as_of_date,
            "constituent_count": self.constituent_count,
            "sha256": self.sha256,
        }


@dataclass
class ConstituentRecord:
    """Normalized constituent row parsed from a verified source."""

    symbol: str
    name: str
    industry: Optional[str] = None
    series: Optional[str] = None
    isin: Optional[str] = None
    exchange: str = "NSE"


class IngestionAction(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    REMOVE = "REMOVE"
    UNCHANGED = "UNCHANGED"
    PRESERVED_CUSTOM = "PRESERVED_CUSTOM"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"


@dataclass
class IngestionItem:
    """Action item planned during constituent ingestion."""

    action: IngestionAction
    symbol: str
    category: UniverseCategory
    current_name: Optional[str] = None
    proposed_name: Optional[str] = None
    reason: str = ""
    error_detail: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "symbol": self.symbol,
            "category": self.category.value,
            "current_name": self.current_name,
            "proposed_name": self.proposed_name,
            "reason": self.reason,
            "error_detail": self.error_detail,
        }


@dataclass
class IngestionPlan:
    """Full plan detailing additions, updates, removals, and preserved records."""

    category: UniverseCategory
    provenance: SourceProvenance
    items: list[IngestionItem] = field(default_factory=list)

    @property
    def additions(self) -> list[IngestionItem]:
        return [i for i in self.items if i.action == IngestionAction.ADD]

    @property
    def updates(self) -> list[IngestionItem]:
        return [i for i in self.items if i.action == IngestionAction.UPDATE]

    @property
    def removals(self) -> list[IngestionItem]:
        return [i for i in self.items if i.action == IngestionAction.REMOVE]

    @property
    def unchanged(self) -> list[IngestionItem]:
        return [i for i in self.items if i.action == IngestionAction.UNCHANGED]

    @property
    def custom_preserved(self) -> list[IngestionItem]:
        return [i for i in self.items if i.action == IngestionAction.PRESERVED_CUSTOM]

    @property
    def conflicts(self) -> list[IngestionItem]:
        return [i for i in self.items if i.action == IngestionAction.CONFLICT]

    @property
    def errors(self) -> list[IngestionItem]:
        return [i for i in self.items if i.action == IngestionAction.ERROR]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "source_name": self.provenance.source_name,
            "source_url": self.provenance.source_url,
            "as_of_date": self.provenance.as_of_date,
            "source_count": self.provenance.constituent_count,
            "counts": {
                "additions": len(self.additions),
                "updates": len(self.updates),
                "removals_proposed": len(self.removals),
                "unchanged": len(self.unchanged),
                "custom_preserved": len(self.custom_preserved),
                "conflicts": len(self.conflicts),
                "errors": len(self.errors),
            },
        }


def parse_constituent_csv(
    csv_content: str,
    category: UniverseCategory,
    provenance: Optional[SourceProvenance] = None,
) -> tuple[list[ConstituentRecord], list[dict[str, Any]]]:
    """
    Parse CSV content from an official index constituent file.

    Returns:
        (constituents, parse_errors)
    """
    if not csv_content.strip():
        raise ValueError("Constituent CSV content is empty.")

    f = StringIO(csv_content)
    reader = csv.reader(f)

    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("Constituent CSV has no header.")

    # Normalize headers
    normalized_header = [h.strip().lower() for h in header]

    # Find symbol column
    symbol_idx = None
    for cand in ("symbol", "security symbol", "ticker"):
        if cand in normalized_header:
            symbol_idx = normalized_header.index(cand)
            break

    # Find name column
    name_idx = None
    for cand in ("company name", "security name", "name"):
        if cand in normalized_header:
            name_idx = normalized_header.index(cand)
            break

    if symbol_idx is None:
        raise ValueError("Constituent CSV is missing required 'Symbol' column.")
    if name_idx is None:
        raise ValueError("Constituent CSV is missing required 'Company Name' column.")

    # Optional column indexes
    industry_idx = normalized_header.index("industry") if "industry" in normalized_header else None
    series_idx = normalized_header.index("series") if "series" in normalized_header else None
    isin_idx = normalized_header.index("isin code") if "isin code" in normalized_header else None

    records: list[ConstituentRecord] = []
    errors: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()

    for line_num, row in enumerate(reader, start=2):
        if not row or not any(cell.strip() for cell in row):
            continue

        if len(row) <= max(symbol_idx, name_idx):
            errors.append({
                "line": line_num,
                "error": f"Row has insufficient columns: {row}",
            })
            continue

        raw_symbol = row[symbol_idx].strip()
        raw_name = row[name_idx].strip()

        if not raw_symbol:
            errors.append({
                "line": line_num,
                "error": "Symbol is empty",
            })
            continue

        norm_symbol = raw_symbol.upper()
        if norm_symbol in seen_symbols:
            errors.append({
                "line": line_num,
                "symbol": norm_symbol,
                "error": f"Duplicate symbol found in source: {norm_symbol}",
            })
            continue

        seen_symbols.add(norm_symbol)
        industry = row[industry_idx].strip() if industry_idx is not None and len(row) > industry_idx else None
        series = row[series_idx].strip() if series_idx is not None and len(row) > series_idx else None
        isin = row[isin_idx].strip() if isin_idx is not None and len(row) > isin_idx else None

        records.append(
            ConstituentRecord(
                symbol=norm_symbol,
                name=raw_name,
                industry=industry,
                series=series,
                isin=isin,
                exchange="NSE",
            )
        )

    return records, errors


def create_ingestion_plan(
    registry: StockUniverseRegistry,
    constituents: list[ConstituentRecord],
    category: UniverseCategory,
    provenance: SourceProvenance,
) -> IngestionPlan:
    """
    Compare verified constituent records with current registry state to construct
    an auditable ingestion plan.

    Safety guarantees:
    - Never deletes or modifies CUSTOM category stocks.
    - Flags category conflicts where a custom stock shares the same symbol.
    - Flags proposed removals of obsolete constituents for explicit review.
    """
    plan = IngestionPlan(category=category, provenance=provenance)
    incoming_map = {c.symbol: c for c in constituents}
    current_stocks = {s.symbol: s for s in registry.list_all()}

    # 1. Inspect incoming source constituents
    for c in constituents:
        existing = current_stocks.get(c.symbol)

        if existing is None:
            # New addition
            plan.items.append(
                IngestionItem(
                    action=IngestionAction.ADD,
                    symbol=c.symbol,
                    category=category,
                    current_name=None,
                    proposed_name=c.name,
                    reason=f"New constituent in {category.value} source",
                )
            )
        elif existing.category == UniverseCategory.CUSTOM:
            # Conflict: Symbol exists as a user-defined custom stock
            plan.items.append(
                IngestionItem(
                    action=IngestionAction.CONFLICT,
                    symbol=c.symbol,
                    category=existing.category,
                    current_name=existing.name,
                    proposed_name=c.name,
                    reason=f"Stock already registered as CUSTOM stock; automatic conversion disallowed",
                )
            )
        elif existing.category != category:
            # Stock registered under different index category (e.g. moved from NIFTY_NEXT_50 to NIFTY_50)
            plan.items.append(
                IngestionItem(
                    action=IngestionAction.UPDATE,
                    symbol=c.symbol,
                    category=category,
                    current_name=existing.name,
                    proposed_name=c.name,
                    reason=f"Index category migration from {existing.category.value} to {category.value}",
                )
            )
        else:
            # Same category: check if name changed or if it is unchanged
            if existing.name != c.name:
                plan.items.append(
                    IngestionItem(
                        action=IngestionAction.UPDATE,
                        symbol=c.symbol,
                        category=category,
                        current_name=existing.name,
                        proposed_name=c.name,
                        reason=f"Company name updated in source",
                    )
                )
            else:
                plan.items.append(
                    IngestionItem(
                        action=IngestionAction.UNCHANGED,
                        symbol=c.symbol,
                        category=category,
                        current_name=existing.name,
                        proposed_name=c.name,
                        reason=f"Constituent and attributes match source exactly",
                    )
                )

    # 2. Check for proposed removals: stocks registered in this category that are absent from source
    for existing_sym, existing in current_stocks.items():
        if existing.category == category and existing_sym not in incoming_map:
            plan.items.append(
                IngestionItem(
                    action=IngestionAction.REMOVE,
                    symbol=existing.symbol,
                    category=category,
                    current_name=existing.name,
                    proposed_name=None,
                    reason=f"Stock was previously registered under {category.value} but is absent from current verified source",
                )
            )
        elif existing.category == UniverseCategory.CUSTOM:
            plan.items.append(
                IngestionItem(
                    action=IngestionAction.PRESERVED_CUSTOM,
                    symbol=existing.symbol,
                    category=UniverseCategory.CUSTOM,
                    current_name=existing.name,
                    proposed_name=None,
                    reason="Custom stock preserved unperturbed",
                )
            )

    return plan


def execute_ingestion(
    registry: StockUniverseRegistry,
    plan: IngestionPlan,
    dry_run: bool = True,
    confirm_removals: bool = False,
) -> dict[str, Any]:
    """
    Execute an ingestion plan.

    Args:
        registry: The active or test StockUniverseRegistry.
        plan: The generated IngestionPlan.
        dry_run: If True, no changes are committed to storage.
        confirm_removals: If True, allows removal of obsolete non-custom index stocks.

    Returns:
        Audit report detailing actions taken or planned.
    """
    result: dict[str, Any] = {
        "category": plan.category.value,
        "dry_run": dry_run,
        "confirm_removals_provided": confirm_removals,
        "as_of_date": plan.provenance.as_of_date,
        "source_name": plan.provenance.source_name,
        "source_url": plan.provenance.source_url,
        "retrieval_timestamp": plan.provenance.retrieval_timestamp.isoformat(),
        "sha256": plan.provenance.sha256,
        "applied": {
            "additions": [],
            "updates": [],
            "removals_executed": [],
            "removals_withheld": [],
            "custom_preserved": [i.symbol for i in plan.custom_preserved],
            "conflicts_skipped": [i.symbol for i in plan.conflicts],
            "errors": [i.to_dict() for i in plan.errors],
        },
        "counts": {
            "added": len(plan.additions),
            "updated": len(plan.updates),
            "removed": 0,
            "removals_withheld": len(plan.removals),
            "unchanged": len(plan.unchanged),
            "custom_preserved": len(plan.custom_preserved),
            "conflicts": len(plan.conflicts),
        },
    }

    if dry_run:
        result["status"] = "DRY_RUN_COMPLETED"
        result["message"] = "Dry-run completed successfully. Persistent storage was NOT modified."
        result["applied"]["additions"] = [i.to_dict() for i in plan.additions]
        result["applied"]["updates"] = [i.to_dict() for i in plan.updates]
        result["applied"]["removals_withheld"] = [i.to_dict() for i in plan.removals]
        return result

    # Execution against registry
    # 1. Additions
    for item in plan.additions:
        if registry.get(item.symbol):
            registry.update_stock(
                symbol=item.symbol,
                name=item.proposed_name,
                category=plan.category,
                membership_verified_at=plan.provenance.retrieval_timestamp,
            )
        else:
            registry.register(
                symbol=item.symbol,
                exchange="NSE",
                category=plan.category,
                name=item.proposed_name,
                membership_verified_at=plan.provenance.retrieval_timestamp,
            )
        result["applied"]["additions"].append(item.symbol)

    # 2. Updates
    for item in plan.updates:
        registry.update_stock(
            symbol=item.symbol,
            name=item.proposed_name,
            category=plan.category,
            membership_verified_at=plan.provenance.retrieval_timestamp,
        )
        result["applied"]["updates"].append(item.symbol)

    # 3. Removals
    if plan.removals:
        if confirm_removals:
            for item in plan.removals:
                registry.remove_stock(item.symbol, allow_custom_removal=False)
                result["applied"]["removals_executed"].append(item.symbol)
            result["counts"]["removed"] = len(result["applied"]["removals_executed"])
            result["counts"]["removals_withheld"] = 0
        else:
            result["applied"]["removals_withheld"] = [i.symbol for i in plan.removals]
            result["counts"]["removed"] = 0
            result["counts"]["removals_withheld"] = len(plan.removals)

    result["status"] = "APPLIED"
    result["message"] = (
        f"Ingestion successfully committed to registry: "
        f"{len(result['applied']['additions'])} added, "
        f"{len(result['applied']['updates'])} updated, "
        f"{result['counts']['removed']} removed."
    )
    return result


def load_canonical_source(
    category: UniverseCategory,
    sources_dir: Optional[Path] = None,
) -> tuple[str, SourceProvenance]:
    """
    Load canonical constituent CSV content and verified provenance metadata
    from local verified source repository.
    """
    base_dir = sources_dir or (Path(__file__).resolve().parents[2] / "data" / "universe" / "sources")
    manifest_file = base_dir / "manifest.json"

    if not manifest_file.exists():
        raise FileNotFoundError(f"Source manifest not found at {manifest_file}")

    import json
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    cat_key = category.value
    if cat_key not in manifest_data.get("sources", {}):
        raise KeyError(f"Category {cat_key} not found in manifest sources.")

    source_meta = manifest_data["sources"][cat_key]
    csv_file = base_dir / Path(source_meta["local_file"]).name

    if not csv_file.exists():
        raise FileNotFoundError(f"Canonical source CSV not found at {csv_file}")

    csv_text = csv_file.read_text(encoding="utf-8")

    # Verify sha256 checksum
    computed_hash = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    if computed_hash != source_meta["sha256"]:
        raise ValueError(
            f"Checksum verification failed for {csv_file}: "
            f"expected {source_meta['sha256']}, got {computed_hash}"
        )

    provenance = SourceProvenance(
        source_name=source_meta["source_name"],
        source_url=source_meta["source_url"],
        local_file=str(csv_file),
        retrieval_timestamp=datetime.fromisoformat(source_meta["retrieval_timestamp"]),
        as_of_date=source_meta["as_of_date"],
        constituent_count=source_meta["constituent_count"],
        sha256=computed_hash,
    )

    return csv_text, provenance
