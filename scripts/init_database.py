"""
Initialize the Correctr SQLite database.

Run from the project root:

    python scripts/init_database.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.database import initialize_database  # noqa: E402


def main() -> None:
    database_path = initialize_database()

    print("Correctr database initialized.")
    print(f"Database path: {database_path}")


if __name__ == "__main__":
    main()
