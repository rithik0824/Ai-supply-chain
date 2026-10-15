"""
Import every CSV file in datasets/ into supply_chain.db.

Each CSV becomes a SQLite table named from the file stem, for example:
  datasets/logistics_performance.csv -> logistics_performance
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATASETS_DIR = BASE_DIR / "datasets"
DB_PATH = BASE_DIR / "supply_chain.db"
CHUNK_SIZE = 50_000


def table_name_for(csv_path: Path) -> str:
    name = csv_path.stem.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    return name or "dataset"


def import_csv(conn: sqlite3.Connection, csv_path: Path, table_name: str) -> int:
    first_chunk = True
    row_count = 0

    for chunk in pd.read_csv(
        csv_path,
        chunksize=CHUNK_SIZE,
        encoding="utf-8-sig",
        encoding_errors="replace",
    ):
        chunk.columns = [col.strip() for col in chunk.columns]
        chunk.to_sql(
            table_name,
            conn,
            if_exists="replace" if first_chunk else "append",
            index=False,
        )
        row_count += len(chunk)
        first_chunk = False

    return row_count


def main() -> None:
    csv_files = sorted(DATASETS_DIR.glob("*.csv"))
    if not csv_files:
        raise SystemExit(f"No CSV files found in {DATASETS_DIR}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_imports (
                table_name TEXT PRIMARY KEY,
                source_file TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        for csv_path in csv_files:
            table_name = table_name_for(csv_path)
            print(f"Importing {csv_path.name} -> {table_name}")
            row_count = import_csv(conn, csv_path, table_name)
            conn.execute(
                """
                INSERT INTO dataset_imports (table_name, source_file, row_count, imported_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(table_name) DO UPDATE SET
                    source_file = excluded.source_file,
                    row_count = excluded.row_count,
                    imported_at = CURRENT_TIMESTAMP
                """,
                (table_name, str(csv_path.relative_to(BASE_DIR)), row_count),
            )
            print(f"  stored {row_count:,} rows")

        conn.commit()

    print(f"\nDone. Tables were created in {DB_PATH}")


if __name__ == "__main__":
    main()
