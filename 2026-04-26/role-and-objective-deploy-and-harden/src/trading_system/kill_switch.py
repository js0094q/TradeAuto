from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ENABLED_VALUES = {"1", "true", "enabled", "on", "yes"}


@dataclass(frozen=True)
class KillSwitch:
    path: Path

    def is_enabled(self) -> bool:
        text = self.path.read_text(encoding="utf-8").strip().lower()
        return text in ENABLED_VALUES

    def enable(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("enabled\n", encoding="utf-8")

    def disable(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("disabled\n", encoding="utf-8")

