"""SignalForge CLI: Auditable Stock Universe Constituent Ingestion & Readiness.

Usage:
  python scripts/ingest_universe_constituents.py [--category NIFTY_50|NIFTY_NEXT_50|ALL] [--dry-run | --apply] [--confirm-removals] [--readiness]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.universe.ingestion import (
    load_canonical_source,
    parse_constituent_csv,
    create_ingestion_plan,
    execute_ingestion,
)
from src.universe.readiness import assess_universe_readiness
from src.universe.registry import StockUniverseRegistry, UniverseCategory


def run_category_ingestion(
    registry: StockUniverseRegistry,
    category: UniverseCategory,
    dry_run: bool,
    confirm_removals: bool,
) -> dict:
    csv_text, provenance = load_canonical_source(category)
    constituents, parse_errors = parse_constituent_csv(csv_text, category, provenance)
    if parse_errors:
        print(f"[{category.value}] Warning: {len(parse_errors)} row parse errors encountered:")
        for err in parse_errors:
            print(f"  Line {err.get('line')}: {err.get('error')}")

    plan = create_ingestion_plan(
        registry=registry,
        constituents=constituents,
        category=category,
        provenance=provenance,
    )

    summary = plan.summary_dict()
    print(f"\n=======================================================")
    print(f" Category: {category.value}")
    print(f" Source: {provenance.source_name} ({provenance.as_of_date})")
    print(f" Source URL: {provenance.source_url}")
    print(f" Verified SHA256: {provenance.sha256[:16]}...")
    print(f" Constituents in Source: {len(constituents)}")
    print(f" Planned Additions: {len(plan.additions)}")
    print(f" Planned Updates: {len(plan.updates)}")
    print(f" Proposed Removals: {len(plan.removals)}")
    print(f" Unchanged: {len(plan.unchanged)}")
    print(f" Custom Stocks Preserved: {len(plan.custom_preserved)}")
    print(f" Conflicts / Errors: {len(plan.conflicts) + len(plan.errors)}")
    print(f"=======================================================")

    if plan.additions:
        print(f"\nSample Additions (first 5 of {len(plan.additions)}):")
        for item in plan.additions[:5]:
            print(f"  + {item.symbol:<12} {item.proposed_name}")

    if plan.removals:
        print(f"\nProposed Removals ({len(plan.removals)}):")
        for item in plan.removals:
            print(f"  - {item.symbol:<12} {item.current_name} ({item.reason})")
        if not confirm_removals:
            print("  --> NOTE: Removals will be withheld unless --confirm-removals is passed.")

    result = execute_ingestion(
        registry=registry,
        plan=plan,
        dry_run=dry_run,
        confirm_removals=confirm_removals,
    )

    print(f"\nStatus: {result['status']}")
    print(f"Message: {result['message']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="SignalForge Stock Universe Ingestion & Readiness CLI")
    parser.add_argument(
        "--category",
        choices=["NIFTY_50", "NIFTY_NEXT_50", "ALL"],
        default="ALL",
        help="Category to ingest (default: ALL)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to registry (default is dry-run)",
    )
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry run without modifying persistent registry (default)",
    )
    parser.add_argument(
        "--confirm-removals",
        action="store_true",
        help="Explicitly authorize deletion of constituents absent from source",
    )
    parser.add_argument(
        "--readiness",
        action="store_true",
        help="Run universe readiness audit after ingestion",
    )
    parser.add_argument(
        "--registry-path",
        default="data/universe_registry.json",
        help="Path to universe registry file (default: data/universe_registry.json)",
    )

    args = parser.parse_args()
    dry_run = not args.apply

    reg_path = Path(args.registry_path)
    print(f"Target Registry: {reg_path}")
    print(f"Execution Mode: {'DRY RUN (no persistence)' if dry_run else 'APPLY (modifying registry)'}")

    registry = StockUniverseRegistry(reg_path)
    initial_count = len(registry.list_all())
    print(f"Current Registered Stocks: {initial_count}")

    cats = (
        [UniverseCategory.NIFTY_50, UniverseCategory.NIFTY_NEXT_50]
        if args.category == "ALL"
        else [UniverseCategory(args.category)]
    )

    results = []
    for cat in cats:
        res = run_category_ingestion(
            registry=registry,
            category=cat,
            dry_run=dry_run,
            confirm_removals=args.confirm_removals,
        )
        results.append(res)

    final_stocks = registry.list_all()
    print(f"\n=======================================================")
    print(f" Final Registry Summary:")
    print(f" Total Registered Stocks: {len(final_stocks)} (started with {initial_count})")
    cat_counts = {}
    for s in final_stocks:
        cat_counts[s.category.value] = cat_counts.get(s.category.value, 0) + 1
    for c_name, c_cnt in sorted(cat_counts.items()):
        print(f"   {c_name}: {c_cnt}")
    print(f"=======================================================")

    if args.readiness:
        print("\nEvaluating Universe Readiness Audit (Strategy: SignalForge_V1)...")
        readiness = assess_universe_readiness(registry, strategy_id="SignalForge_V1")
        print(f"Readiness Summary:")
        print(f"  States: {readiness['summary']['by_state']}")
        print(f"  Categories: {readiness['summary']['by_category']}")
        print(f"  Historical Data Ready (>= 500 candles): {readiness['summary']['data_ready_count']}")
        print(f"  Approved Count: {readiness['summary']['approved_count']}")


if __name__ == "__main__":
    main()
