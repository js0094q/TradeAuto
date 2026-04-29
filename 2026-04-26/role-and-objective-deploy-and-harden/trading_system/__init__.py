from __future__ import annotations

from pathlib import Path


_SRC_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "trading_system"
__path__ = [str(_SRC_PACKAGE_DIR)]
__all__ = ["__version__"]
__version__ = "0.1.0"
