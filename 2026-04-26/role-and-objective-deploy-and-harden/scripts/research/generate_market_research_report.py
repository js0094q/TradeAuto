#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


REPORTS = (
    "repo_inventory.md",
    "data_source_audit.md",
    "universe_design.md",
    "historical_regime_review.md",
    "regime_research.md",
    "strategy_family_review.md",
    "signal_dictionary.md",
    "backtest_validation_report.md",
    "provider_backtest_results.md",
    "walk_forward_validation.md",
    "ready_strategy_validation.md",
    "strategy_scorecard.md",
    "shadow_validation_plan.md",
    "strategy_pattern_mining.md",
    "external_source_crosscheck.md",
    "strategy_trigger_event_catalog.md",
    "execution_assumptions.md",
    "options_signal_research.md",
    "crypto_strategy_research.md",
    "realtime_shadow_validation.md",
    "rejection_rules.md",
    "live_candidate_scorecard.md",
    "risk_control_mapping.md",
    "ops_integration_review.md",
)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    report_dir = root / "research" / "market_signals"
    status = {name: (report_dir / name).exists() for name in REPORTS}
    print(
        json.dumps(
            {
                "report_dir": str(report_dir),
                "all_reports_present": all(status.values()),
                "reports": status,
                "research_only": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
