from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import release_transition_probe as probe  # noqa: E402


@dataclass
class FakeResult:
    value: object

    def __iter__(self):
        return iter(self.value)

    def scalar_one(self) -> object:
        return self.value


class FakeTransaction:
    def __init__(self) -> None:
        self.rolled_back = False

    def rollback(self) -> None:
        self.rolled_back = True


class FakeConnection:
    def __init__(self, *, heads: list[tuple[str]] | None = None, counts=None) -> None:
        self.heads = heads or []
        self.counts = list(counts or [])
        self.transaction = FakeTransaction()

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def begin(self) -> FakeTransaction:
        return self.transaction

    def execute(self, statement) -> FakeResult:
        query = str(statement)
        if "version_num" in query:
            return FakeResult(self.heads)
        if query.startswith("SELECT count"):
            return FakeResult(self.counts.pop(0))
        return FakeResult(0)


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.disposed = False

    def connect(self) -> FakeConnection:
        return self.connection

    def dispose(self) -> None:
        self.disposed = True


class FakeInspector:
    def __init__(self, tables: list[str]) -> None:
        self.tables = tables

    def get_table_names(self, *, schema: str) -> list[str]:
        assert schema == "public"
        return self.tables


def test_classify_accepts_only_exact_source_heads(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection(heads=[("head-a",), ("head-b",)])
    engine = FakeEngine(connection)
    monkeypatch.setattr(probe, "_engine", lambda: engine)
    monkeypatch.setattr(
        probe, "inspect", lambda _connection: FakeInspector(["alembic_version", "runs"])
    )
    monkeypatch.setattr(
        probe.ScriptDirectory,
        "from_config",
        lambda _config: type("Heads", (), {"get_heads": lambda self: ["head-b", "head-a"]})(),
    )

    assert probe.classify() == {"classification": "source", "heads": ["head-a", "head-b"]}
    assert connection.transaction.rolled_back
    assert engine.disposed


def test_classify_rejects_application_tables_without_alembic(monkeypatch) -> None:
    engine = FakeEngine(FakeConnection())
    monkeypatch.setattr(probe, "_engine", lambda: engine)
    monkeypatch.setattr(probe, "inspect", lambda _connection: FakeInspector(["runs"]))

    with pytest.raises(probe.TransitionProbeError, match="without alembic_version"):
        probe.classify()


def test_active_work_reports_all_bounded_categories(monkeypatch) -> None:
    connection = FakeConnection(counts=[0, 2, 0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(probe, "_engine", lambda: FakeEngine(connection))

    result = probe.active_work()

    assert result["status"] == "blocked"
    assert result["counts"] == {
        "runs": 0,
        "allocations": 2,
        "leases": 0,
        "controlRequests": 0,
        "initializations": 0,
        "loadNodeStatus": 0,
        "loadNodeRuns": 0,
        "reports": 0,
    }


@pytest.mark.parametrize(
    ("configured_url", "expected_url"),
    [
        ("postgresql://example", "postgresql+psycopg://example"),
        ("postgresql+psycopg://example", "postgresql+psycopg://example"),
    ],
)
def test_engine_uses_psycopg_and_sets_fixed_postgres_timeouts(
    monkeypatch, configured_url: str, expected_url: str
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("DATABASE_URL", configured_url)

    def fake_create_engine(url: str, **kwargs):
        captured.update(url=url, **kwargs)
        return object()

    monkeypatch.setattr(probe, "create_engine", fake_create_engine)

    probe._engine()

    assert captured["url"] == expected_url
    assert captured["connect_args"] == {
        "connect_timeout": 10,
        "options": "-c statement_timeout=10000 -c lock_timeout=5000",
    }
