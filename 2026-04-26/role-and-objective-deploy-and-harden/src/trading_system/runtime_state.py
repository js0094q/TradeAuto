from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def ensure_runtime_state(
    *,
    shared_dir: Path,
    log_dir: Path,
    kill_switch_file: Path,
    mode: str = "paper",
) -> dict[str, bool]:
    results = {
        "shared_dir": False,
        "log_dir": False,
        "kill_switch_file": False,
        "paper_order_state": False,
        "paper_status_state": False,
    }

    shared_dir.mkdir(parents=True, exist_ok=True)
    results["shared_dir"] = True

    log_dir.mkdir(parents=True, exist_ok=True)
    results["log_dir"] = True

    kill_switch_file.parent.mkdir(parents=True, exist_ok=True)
    if not kill_switch_file.exists():
        kill_switch_file.write_text("enabled\n", encoding="utf-8")
    results["kill_switch_file"] = True

    state_dir = shared_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    order_state_path = state_dir / "paper_entry_orders.json"
    if not order_state_path.exists():
        order_state_payload = {
            "client_order_ids": [],
            "orders": {},
            "updated_at": _now_iso(),
        }
        order_state_path.write_text(
            json.dumps(order_state_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    results["paper_order_state"] = True

    status_path = state_dir / "paper_strategy_status.json"
    if not status_path.exists():
        status_path.write_text(
            json.dumps(
                {
                    "ok": False,
                    "mode": mode,
                    "timestamp": _now_iso(),
                    "live_trading_changed": False,
                    "kill_switch_enabled": True,
                    "paper_execution": {"status": "not_initialized", "orders": []},
                    "strategies": [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    results["paper_status_state"] = True
    return results
