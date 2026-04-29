from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TELEGRAM_TOKEN_PATTERN = re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{30,}\b")
SKIP_TOP_LEVEL_DIRS = {
    ".git",
    ".venv",
    ".next",
    "node_modules",
    "venv",
}
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tgz",
    ".whl",
}


class RepoHygieneTests(unittest.TestCase):
    def test_runtime_telegram_update_file_is_not_checked_in(self) -> None:
        self.assertFalse(
            (REPO_ROOT / ".telegrambotupdate.txt").exists(),
            ".telegrambotupdate.txt must stay untracked because it may contain live secrets.",
        )

    def test_no_hardcoded_telegram_bot_tokens(self) -> None:
        offenders: list[str] = []
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(REPO_ROOT)
            if relative.parts and relative.parts[0] in SKIP_TOP_LEVEL_DIRS:
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if TELEGRAM_TOKEN_PATTERN.search(text):
                offenders.append(str(relative))
        self.assertFalse(
            offenders,
            "Telegram bot token pattern found in tracked files: " + ", ".join(sorted(offenders)),
        )


if __name__ == "__main__":
    unittest.main()
