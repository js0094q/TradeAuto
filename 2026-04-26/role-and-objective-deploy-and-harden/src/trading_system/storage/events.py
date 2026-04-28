from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def append_jsonl(path: str | Path, event: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.now(UTC).isoformat(), **event}
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def logs_are_writable(log_dir: str | Path) -> bool:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write_probe"
    probe.write_text("ok\n", encoding="utf-8")
    probe.unlink(missing_ok=True)
    return True

