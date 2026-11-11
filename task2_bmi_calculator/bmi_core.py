"""Shared BMI logic and SQLite persistence used by both the CLI and the GUI."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "bmi_records.db"

CATEGORY_COLOURS = {
    "Underweight": "#2e86de",
    "Normal": "#2ecc71",
    "Overweight": "#f39c12",
    "Obese": "#e74c3c",
}


def calculate_bmi(weight_kg: float, height_m: float) -> float:
    if weight_kg <= 0 or height_m <= 0:
        raise ValueError("Weight and height must be positive numbers.")
    return weight_kg / (height_m ** 2)


def classify_bmi(bmi: float) -> str:
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"


def parse_positive_float(raw: str, field: str) -> float:
    """Convert text to a positive float or raise ValueError with a helpful message."""
    raw = raw.strip()
    if not raw:
        raise ValueError(f"{field} cannot be empty.")
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{field} must be a number (for example 70 or 1.75), not '{raw}'.") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{field} must be a real number.")
    if value <= 0:
        raise ValueError(f"{field} must be greater than zero.")
    return value


def validate_ranges(weight_kg: float, height_m: float) -> None:
    """Sanity limits so typos such as 175 (cm) entered as metres are caught."""
    if not 1 <= weight_kg <= 500:
        raise ValueError("Weight should be between 1 and 500 kg.")
    if not 0.3 <= height_m <= 2.8:
        raise ValueError("Height should be in metres between 0.3 and 2.8 (e.g. 1.75, not 175).")


class DatabaseError(Exception):
    """Raised when a read/write on the BMI database fails."""


class BMIDatabase:
    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        try:
            return sqlite3.connect(self.path)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not open the database: {exc}") from exc

    @contextmanager
    def _transaction(self):
        """Commit on success, roll back on error, and always close the connection.

        (A bare `with sqlite3.connect(...)` only manages the transaction - it never closes
        the connection, which leaks file handles.)
        """
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        try:
            with self._transaction() as conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS records (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           username TEXT NOT NULL,
                           weight_kg REAL NOT NULL,
                           height_m REAL NOT NULL,
                           bmi REAL NOT NULL,
                           category TEXT NOT NULL,
                           recorded_at TEXT NOT NULL)"""
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON records(username)")
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not initialise the database: {exc}") from exc

    def add_record(self, username: str, weight: float, height: float, bmi: float,
                   category: str, when: datetime | None = None) -> None:
        when = when or datetime.now()
        try:
            with self._transaction() as conn:
                conn.execute(
                    "INSERT INTO records (username, weight_kg, height_m, bmi, category, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (username.strip(), weight, height, round(bmi, 2), category,
                     when.strftime("%Y-%m-%d %H:%M:%S")),
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not save the record: {exc}") from exc

    def users(self) -> list[str]:
        try:
            with self._transaction() as conn:
                rows = conn.execute("SELECT DISTINCT username FROM records ORDER BY username").fetchall()
            return [r[0] for r in rows]
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not read users: {exc}") from exc

    def history(self, username: str) -> list[tuple]:
        """Return (recorded_at, weight, height, bmi, category) oldest first."""
        try:
            with self._transaction() as conn:
                return conn.execute(
                    "SELECT recorded_at, weight_kg, height_m, bmi, category FROM records "
                    "WHERE username = ? ORDER BY recorded_at, id", (username.strip(),)
                ).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not read history: {exc}") from exc

    def delete_user(self, username: str) -> int:
        try:
            with self._transaction() as conn:
                cur = conn.execute("DELETE FROM records WHERE username = ?", (username.strip(),))
                return cur.rowcount
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not delete records: {exc}") from exc
