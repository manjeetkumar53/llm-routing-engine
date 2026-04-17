from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path("telemetry.db")

_DDL = """
CREATE TABLE IF NOT EXISTS events (
    request_id      TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    selected_tier   TEXT NOT NULL,
    latency_ms      REAL NOT NULL,
    estimated_cost_usd REAL NOT NULL,
    experiment_mode TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    complexity_score REAL NOT NULL DEFAULT 0.0
);
"""


@dataclass
class TelemetryEvent:
    selected_tier: str
    latency_ms: float
    estimated_cost_usd: float
    experiment_mode: str = "router_v1"
    input_tokens: int = 0
    output_tokens: int = 0
    complexity_score: float = 0.0
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TelemetryStore:
    def __init__(self, db_path: Path = _DEFAULT_DB) -> None:
        self._db_path = db_path
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_DDL)

    def add(self, event: TelemetryEvent) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO events
                    (request_id, created_at, selected_tier, latency_ms,
                     estimated_cost_usd, experiment_mode, input_tokens,
                     output_tokens, complexity_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.request_id,
                    event.created_at,
                    event.selected_tier,
                    event.latency_ms,
                    event.estimated_cost_usd,
                    event.experiment_mode,
                    event.input_tokens,
                    event.output_tokens,
                    event.complexity_score,
                ),
            )

    def summary(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            if total == 0:
                return {
                    "total_requests": 0,
                    "by_tier": {"cheap": 0, "premium": 0},
                    "average_latency_ms": 0.0,
                    "average_cost_usd": 0.0,
                    "by_experiment_mode": {},
                }

            rows = conn.execute(
                """
                SELECT
                    selected_tier,
                    experiment_mode,
                    AVG(latency_ms)          AS avg_latency,
                    AVG(estimated_cost_usd)  AS avg_cost,
                    COUNT(*)                 AS cnt
                FROM events
                GROUP BY selected_tier, experiment_mode
                """
            ).fetchall()

            by_tier: dict[str, int] = {"cheap": 0, "premium": 0}
            by_mode: dict[str, int] = {}
            total_latency = 0.0
            total_cost = 0.0
            event_count = 0

            for row in rows:
                cnt = row["cnt"]
                by_tier[row["selected_tier"]] = by_tier.get(row["selected_tier"], 0) + cnt
                by_mode[row["experiment_mode"]] = by_mode.get(row["experiment_mode"], 0) + cnt
                total_latency += row["avg_latency"] * cnt
                total_cost += row["avg_cost"] * cnt
                event_count += cnt

            return {
                "total_requests": total,
                "by_tier": by_tier,
                "average_latency_ms": round(total_latency / event_count, 2),
                "average_cost_usd": round(total_cost / event_count, 8),
                "by_experiment_mode": by_mode,
            }

    def all_events(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY created_at").fetchall()
            return [dict(r) for r in rows]


# Keep backward-compatible alias used by tests
InMemoryTelemetryStore = TelemetryStore
