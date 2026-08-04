"""
Maintenance script to clear all records from the user_answers table.
- Attempts TRUNCATE TABLE first (fast and resets AUTO_INCREMENT)
- Falls back to DELETE FROM user_answers if TRUNCATE is not permitted
- Prints before/after counts for verification
"""
from pathlib import Path
import sys

# Ensure project root is on sys.path so we can import database.db_connector
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from database.db_connector import get_connection


def _get_count(cursor) -> int:
    """Return count of records in user_answers."""
    cursor.execute("SELECT COUNT(*) AS cnt FROM user_answers")
    row = cursor.fetchone()
    return int(row[0] if isinstance(row, (list, tuple)) else row.get("cnt", 0))


def clear_user_answers() -> None:
    """Clear all rows in user_answers table safely and report counts."""
    conn = get_connection()
    if not conn:
        raise RuntimeError("无法连接数据库：get_connection() 返回 None")
    try:
        cursor = conn.cursor()
        before = _get_count(cursor)
        try:
            # Prefer TRUNCATE for speed and to reset auto-increment
            cursor.execute("TRUNCATE TABLE user_answers")
            conn.commit()
        except Exception:
            # Fall back to DELETE if TRUNCATE not permitted
            cursor.execute("DELETE FROM user_answers")
            conn.commit()
        after = _get_count(cursor)
        print(f"[clear_user_answers] Before: {before}, After: {after}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    clear_user_answers()
    print("[clear_user_answers] Done.")