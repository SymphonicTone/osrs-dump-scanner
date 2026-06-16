import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List


class PriceHistory:
    def __init__(self, db_path: str = "data/price_history.db"):
        self.db_path = db_path
        self.con = sqlite3.connect(db_path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()
        self._init_schema()

    # Creates tables if they currently do not exist
    def _init_schema(self):
        self.cur.executescript("""
            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id     TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL,
                high        INTEGER NOT NULL,
                low         INTEGER NOT NULL,
                high_volume INTEGER NOT NULL DEFAULT 0,
                low_volume  INTEGER NOT NULL DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_item_timestamp
                ON price_history (item_id, timestamp);
                               
            CREATE TABLE IF NOT EXISTS last_vacuum (
                id          INTEGER PRIMARY KEY CHECK (id = 1),
                vacuumed_at TEXT NOT NULL
            );
        """)
        self.con.commit()

    # Writes a price snapshot only when high or low price has changes since the last record
    def write_if_changed(
        self,
        item_id: str,
        high: int,
        low: int,
        high_volume: int,
        low_volume: int,
    ) -> bool:
        last = self._get_last_record(item_id)
        if last and last["high"] == high and last["low"] == low:
            return False

        now = datetime.now(timezone.utc).isoformat()
        self.cur.execute(
            """
            INSERT INTO price_history(item_id, timestamp, high, low, high_volume, low_volume)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(item_id), now, high, low, high_volume, low_volume),
        )
        self.con.commit()
        return True

    # Writes a list of price snapshots in bulk, skipping unchanged prices
    def write_batch(self, records: List[Dict[str, Any]]) -> int:
        written = 0
        for r in records:
            did_write = self.write_if_changed(
                item_id=str(r["item_id"]),
                high=int(r["high"]),
                low=int(r["low"]),
                high_volume=int(r.get("high_volume", 0)),
                low_volume=int(r.get("low_volume", 0)),
            )
            if did_write:
                written += 1
        return written

    # Returns the most recent price record
    def _get_last_record(self, item_id: str) -> sqlite3.Row | None:
        self.cur.execute(
            """
            SELECT * FROM price_history
            WHERE item_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (str(item_id),),
        )
        return self.cur.fetchone()

    # Returns all price records for a specific item within a specified time period
    def get_history(self, item_id: str, days: int = 30) -> List[sqlite3.Row]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        self.cur.execute(
            """
            SELECT * FROM price_history
            WHERE item_id == ? AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (str(item_id), cutoff),
        )
        return self.cur.fetchall()

    # Returns how many days of history an item has
    def get_days_of_history(self, item_id: str) -> float:
        self.cur.execute(
            """
            SELECT MIN(timestamp), MAX(timestamp)
            FROM price_history
            WHERE item_id = ?
            """,
            (str(item_id),),
        )
        row = self.cur.fetchone()
        if not row or not row[0]:
            return 0.0
        earliest = datetime.fromisoformat(row[0])
        latest = datetime.fromisoformat(row[1])
        return (latest - earliest).total_seconds() / 86400

    # Calculates historical baseline statistics for an item over a specified amount of days
    def get_baseline(self, item_id: str, days: int = 30) -> Dict[str, Any] | None:
        history = self.get_history(item_id, days)

        if len(history) < 5:
            return None

        highs = [r["high"] for r in history]
        lows = [r["low"] for r in history]
        spreads = [r["high"] - r["low"] for r in history]
        volumes = [r["high_volume"] + r["low_volume"] for r in history]

        mean_high = sum(highs) / len(highs)
        mean_low = sum(lows) / len(lows)
        mean_spread = sum(spreads) / len(spreads)
        mean_volume = sum(volumes) / len(volumes)

        std_high = (sum((h - mean_high) ** 2 for h in highs) / len(highs)) ** 0.5
        std_low = (sum((l - mean_low) ** 2 for l in lows) / len(lows)) ** 0.5

        days_of_history = self.get_days_of_history(item_id)

        return {
            "mean_high": round(mean_high, 2),
            "mean_low": round(mean_low, 2),
            "mean_spread": round(mean_spread, 2),
            "std_high": round(std_high, 2),
            "std_low": round(std_low, 2),
            "mean_volume": round(mean_volume, 2),
            "days_of_history": round(days_of_history, 1),
            "record_count": len(history),
        }

    # Scores how far the current price deviates from historical baseline
    def get_mean_reversion_score(
        self,
        item_id: str,
        current_high: int,
        current_low: int,
        min_days: float = 7.0,
        days_lookback: int = 30,
    ) -> Dict[str, Any] | None:
        baseline = self.get_baseline(item_id, days_lookback)
        if not baseline:
            return None

        if baseline["days_of_history"] < min_days:
            return None

        high_z = (
            (current_high - baseline["mean_high"]) / baseline["std_high"]
            if baseline["std_high"] > 0
            else 0
        )

        low_z = (
            (current_low - baseline["mean_low"]) / baseline["std_low"]
            if baseline["std_low"] > 0
            else 0
        )

        current_spread = current_high - current_low
        spread_vs_mean = (
            current_spread / baseline["mean_spread"]
            if baseline["mean_spread"] > 0
            else 0
        )

        if low_z < -1.0 and high_z < -0.5:
            opportunity = "buy"
        elif low_z > 1.0 and high_z > 0.5:
            opportunity = "sell"
        elif spread_vs_mean > 1.5:
            opportunity = "wide_spread"
        else:
            opportunity = "none"

        return {
            "high_z_score": round(high_z, 3),
            "low_z_score": round(low_z, 3),
            "spread_vs_mean": round(spread_vs_mean, 3),
            "suggested_buy": int(baseline["mean_low"]),
            "suggested_sell": int(baseline["mean_high"]),
            "opportunity": opportunity,
            "baseline": baseline,
        }

    # Deletes records older than days_to_keep and returns the number of records deleted
    def prune_old_records(self, days_to_keep: int = 35) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()
        self.cur.execute(
            "DELETE FROM price_history WHERE timestamp < ?",
            (cutoff,),
        )
        deleted = self.cur.rowcount
        self.con.commit()
        print(f"[DB] Pruned {deleted:,} records older than {days_to_keep} days.")
        return deleted

    # Runs vacuum to reclaim freed disk space if it hasn't been run recently
    def vacuum_if_due(self) -> bool:
        self.cur.execute("SELECT vacuumed_at FROM last_vacuum WHERE id = 1")
        row = self.cur.fetchone()

        if row:
            last = datetime.fromisoformat(row["vacuumed_at"])
            if datetime.now(timezone.utc) - last < timedelta(days=7):
                return False

        self.con.execute("VACUUM")
        now = datetime.now(timezone.utc).isoformat()
        self.cur.execute(
            "INSERT INTO last_vacuum (id, vacuumed_at) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET vacuumed_at = excluded.vacuumed_at",
            (now,),
        )
        self.con.commit()
        print("[DB] VACUUM complete.")
        return True

    # Returns basic database stats for the /status command
    def get_stats(self) -> Dict[str, Any]:
        self.cur.execute("SELECT COUNT(*) FROM price_history")
        total_records = self.cur.fetchone()[0]

        self.cur.execute("SELECT COUNT(DISTINCT item_id) FROM price_history")
        total_items = self.cur.fetchone()[0]

        self.cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM price_history")
        row = self.cur.fetchone()
        oldest = row[0] or "N/A"
        newest = row[1] or "N/A"

        return {
            "total_records": total_records,
            "total_items": total_items,
            "oldest_record": oldest,
            "newest_record": newest,
        }

    def close(self):
        self.con.close()
