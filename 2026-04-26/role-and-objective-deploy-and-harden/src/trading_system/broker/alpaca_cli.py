from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CliResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class AlpacaCli:
    profile: str
    binary: str = "alpaca"

    def run(self, *args: str, timeout: int = 30) -> CliResult:
        command = [self.binary, *args]
        if self.profile:
            command.extend(["--profile", self.profile])
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CliResult(
            ok=completed.returncode == 0,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def doctor(self) -> CliResult:
        return self.run("doctor")

