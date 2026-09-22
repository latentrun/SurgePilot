"""Read-only database probe for installed release transitions."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


class TransitionProbeError(RuntimeError):
    """Raised when transition state cannot be classified safely."""


def _timeout(_signum: int, _frame: Any) -> None:
    raise TransitionProbeError("transition probe exceeded its total deadline")


def _engine():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise TransitionProbeError("DATABASE_URL is required")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(
        database_url,
        connect_args={
            "connect_timeout": 10,
            "options": "-c statement_timeout=10000 -c lock_timeout=5000",
        },
        pool_pre_ping=False,
    )


def classify() -> dict[str, object]:
    engine = _engine()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("SET TRANSACTION READ ONLY"))
            tables = set(inspect(connection).get_table_names(schema="public"))
            if not tables:
                result: dict[str, object] = {"classification": "empty"}
            elif "alembic_version" not in tables:
                raise TransitionProbeError("application tables exist without alembic_version")
            else:
                actual = {
                    str(row[0])
                    for row in connection.execute(
                        text("SELECT version_num FROM public.alembic_version")
                    )
                }
                expected = set(ScriptDirectory.from_config(Config("/app/alembic.ini")).get_heads())
                if actual != expected:
                    raise TransitionProbeError("database migration heads do not match source")
                result = {"classification": "source", "heads": sorted(actual)}
            transaction.rollback()
            return result
    finally:
        engine.dispose()


ACTIVE_QUERIES = {
    "runs": "SELECT count(*) FROM runs WHERE state IN ('initializing','running','stopping')",
    "allocations": "SELECT count(*) FROM run_node_allocations WHERE state IN ('initializing','running','stopping')",
    "leases": "SELECT count(*) FROM node_leases WHERE released_at IS NULL",
    "controlRequests": "SELECT count(*) FROM run_control_requests WHERE status IN ('pending','running')",
    "initializations": "SELECT count(*) FROM load_node_initialization_attempts WHERE status IN ('queued','running')",
    "loadNodeStatus": "SELECT count(*) FROM load_nodes WHERE status IN ('initializing','busy')",
    "loadNodeRuns": "SELECT count(*) FROM load_nodes WHERE current_run_id IS NOT NULL",
    "reports": "SELECT count(*) FROM run_report_summaries WHERE parse_status = 'pending'",
}


def active_work() -> dict[str, object]:
    engine = _engine()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("SET TRANSACTION READ ONLY"))
            counts = {
                category: int(connection.execute(text(query)).scalar_one())
                for category, query in ACTIVE_QUERIES.items()
            }
            transaction.rollback()
            return {
                "status": "blocked" if any(counts.values()) else "quiescent",
                "counts": counts,
            }
    finally:
        engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("classify", "active-work"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(60)
    try:
        result = classify() if args.mode == "classify" else active_work()
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - one fail-closed probe diagnostic.
        print(f"Release transition probe failed: {exc}", file=sys.stderr)
        return 2
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
