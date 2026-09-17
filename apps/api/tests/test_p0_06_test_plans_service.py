from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.services import test_plans as test_plan_services
from app.services.test_plans import (
    build_test_plan_taurus_document_from_snapshot,
    expected_concurrency_per_node,
    sla_condition_symbol,
    sla_threshold_text,
)


def enabled_item(concurrency: int) -> dict:
    return {
        "enabled": True,
        "loadSettings": {
            "concurrencyPerNode": concurrency,
            "rampUpSeconds": 0,
            "holdForSeconds": 60,
            "iterations": None,
            "targetRps": None,
            "steps": None,
            "delaySeconds": 0,
        },
    }


def test_expected_concurrency_uses_max_for_sequential_and_sum_for_parallel() -> None:
    items = [enabled_item(10), enabled_item(25), {**enabled_item(99), "enabled": False}]

    assert expected_concurrency_per_node("sequential", items) == 25
    assert expected_concurrency_per_node("parallel", items) == 35


def test_not_runnable_reasons_loads_rows_when_children_are_omitted(monkeypatch) -> None:
    plan = SimpleNamespace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        run_mode="sequential",
        pool_type=None,
        selected_node_id=None,
        env_group_id=None,
    )

    monkeypatch.setattr(
        test_plan_services,
        "_rows_for_plan",
        lambda db, *, plan_id: (
            [],
            [SimpleNamespace(enabled=True), SimpleNamespace(enabled=False)],
        ),
    )

    reasons = test_plan_services.not_runnable_reasons(SimpleNamespace(), plan)

    assert "no_enabled_scenarios" in reasons
    assert "load_node_required" in reasons


def test_sla_condition_and_threshold_mapping() -> None:
    assert sla_condition_symbol("gt") == ">"
    assert sla_condition_symbol("gte") == ">="
    assert sla_threshold_text({"value": 500, "unit": "ms"}) == "500ms"
    assert sla_threshold_text({"value": 2, "unit": "s"}) == "2s"
    assert sla_threshold_text({"value": 95, "unit": "percent"}) == "95%"
    assert sla_threshold_text({"value": 100, "unit": "count"}) == 100
    assert sla_threshold_text({"value": 512, "unit": "kb"}) == "512kB"


def test_sla_label_validation_requires_an_exact_generated_sampler_label() -> None:
    rule = {
        "enabled": True,
        "label": "GET /v1/users",
    }

    try:
        test_plan_services._validate_sla_rule_labels(
            [rule], {"GET /v1/users [step:step-id item:item-id]"}
        )
    except AppError as exc:
        assert exc.code == "VALIDATION_ERROR"
        assert exc.details == [
            {
                "field": "slaRules[0].label",
                "code": "unknown_sampler_label",
                "message": "SLA Rule label must match a generated sampler label.",
            }
        ]
    else:
        raise AssertionError("Expected the unknown sampler label to be rejected.")


def test_standard_builder_emits_multiple_executions_force_ctg_and_passfail() -> None:
    snapshot = {
        "runType": "standard",
        "testPlan": {"runMode": "parallel"},
        "scenarioItems": [
            {
                "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
                "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
                "visualScenario": {"requests": []},
                "loadSettings": {
                    "concurrencyPerNode": 10,
                    "rampUpSeconds": 60,
                    "holdForSeconds": 300,
                    "iterations": None,
                    "targetRps": 100,
                    "steps": 5,
                    "delaySeconds": 0,
                },
            },
            {
                "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                "visualScenario": {"requests": []},
                "loadSettings": {
                    "concurrencyPerNode": 3,
                    "rampUpSeconds": 0,
                    "holdForSeconds": None,
                    "iterations": 2,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 1,
                },
            },
        ],
        "slaRules": [
            {
                "enabled": True,
                "subject": "avg_rt",
                "label": None,
                "condition": "gt",
                "threshold": {"value": 500, "unit": "ms"},
                "timeframeLogic": "for",
                "timeframeSeconds": 10,
                "action": "continue",
            },
            {
                "enabled": True,
                "subject": "hits",
                "label": None,
                "condition": "gt",
                "threshold": {"value": 100, "unit": "count"},
                "timeframeLogic": None,
                "timeframeSeconds": None,
                "action": "continue",
            },
        ],
    }

    document = build_test_plan_taurus_document_from_snapshot(
        snapshot, jmeter_path="/opt/jmeter/bin/jmeter", jmeter_version="5.6.3"
    )

    assert len(document["execution"]) == 2
    assert document["modules"]["jmeter"]["force-ctg"] is True
    assert document["modules"]["jmeter"]["memory-xmx"] == "4G"
    assert document["modules"]["local"] == {"class": "bzt.modules.provisioning.Local"}
    assert "sequential" not in document["modules"]["local"]
    assert document["execution"][0]["steps"] == 5
    assert document["execution"][0]["throughput"] == 100
    assert document["execution"][1]["iterations"] == 2
    assert document["execution"][1]["delay"] == "1s"
    passfail = next(item for item in document["reporting"] if item["module"] == "passfail")
    assert passfail["criteria"][0]["subject"] == "avg-rt"
    assert passfail["criteria"][0]["threshold"] == "500ms"
    assert passfail["criteria"][1]["subject"] == "hits"
    assert passfail["criteria"][1]["threshold"] == 100


def test_builder_emits_self_contained_taurus_module_aliases_for_no_system_configs() -> None:
    snapshot = {
        "runType": "standard",
        "testPlan": {"runMode": "sequential"},
        "scenarioItems": [
            {
                "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
                "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
                "visualScenario": {"requests": []},
                "loadSettings": {
                    "concurrencyPerNode": 1,
                    "rampUpSeconds": 0,
                    "holdForSeconds": 10,
                    "iterations": None,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
        ],
        "slaRules": [
            {
                "enabled": True,
                "subject": "avg_rt",
                "condition": "gt",
                "threshold": {"value": 500, "unit": "ms"},
                "action": "fail",
            }
        ],
    }

    document = build_test_plan_taurus_document_from_snapshot(
        snapshot, jmeter_path="/opt/jmeter/bin/jmeter", jmeter_version="5.6.3"
    )

    modules = document["modules"]
    assert document["settings"]["aggregator"] == "consolidator"
    assert modules["jmeter"]["class"] == "bzt.modules.jmeter.JMeterExecutor"
    assert modules["jmeter"]["fix-log4j"] is False
    assert modules["jmeter"]["fix-jars"] is False
    assert modules["jmeter"]["protocol-handlers"]["http"] == "bzt.jmx.http.HTTPProtocolHandler"
    assert modules["local"]["class"] == "bzt.modules.provisioning.Local"
    assert modules["consolidator"]["class"] == "bzt.modules.aggregator.ConsolidatingAggregator"
    assert modules["final-stats"]["class"] == "bzt.modules.reporting.FinalStatus"
    assert modules["console"]["class"] == "bzt.modules.console.ConsoleStatusReporter"
    assert modules["passfail"]["class"] == "bzt.modules.passfail.PassFailStatus"


def test_debug_builder_is_sequential_low_risk_and_omits_passfail() -> None:
    snapshot = {
        "runType": "debug",
        "testPlan": {"runMode": "parallel"},
        "scenarioItems": [
            {
                "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
                "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
                "visualScenario": {"requests": []},
                "loadSettings": {
                    "concurrencyPerNode": 1,
                    "rampUpSeconds": 0,
                    "holdForSeconds": None,
                    "iterations": 1,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
        ],
        "slaRules": [
            {
                "enabled": True,
                "subject": "p95",
                "condition": "gt",
                "threshold": {"value": 500, "unit": "ms"},
                "action": "stop",
            }
        ],
    }

    document = build_test_plan_taurus_document_from_snapshot(
        snapshot, jmeter_path="/opt/jmeter/bin/jmeter", jmeter_version="5.6.3"
    )

    assert document["modules"]["local"] == {
        "class": "bzt.modules.provisioning.Local",
        "sequential": True,
    }
    assert document["execution"] == [
        {
            "executor": "jmeter",
            "scenario": "scenario_01HZX3Y9M0E9W7Z6M5QK9S8P7A",
            "concurrency": 1,
            "iterations": 1,
        }
    ]
    assert all(item != "passfail" for item in document.get("reporting", []))
    assert not any(
        isinstance(item, dict) and item.get("module") == "passfail"
        for item in document.get("reporting", [])
    )


def test_builder_keeps_repeated_scenario_items_distinct() -> None:
    scenario_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7S"
    item_ids = ["01HZX3Y9M0E9W7Z6M5QK9S8P7A", "01HZX3Y9M0E9W7Z6M5QK9S8P7B"]
    snapshot = {
        "runType": "standard",
        "testPlan": {"runMode": "sequential"},
        "scenarioItems": [
            {
                "itemId": item_id,
                "scenarioId": scenario_id,
                "visualScenario": {"requests": [{"label": item_id}]},
                "loadSettings": {
                    "concurrencyPerNode": 1,
                    "rampUpSeconds": 0,
                    "holdForSeconds": 1,
                    "iterations": None,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
            for item_id in item_ids
        ],
        "slaRules": [],
    }

    document = build_test_plan_taurus_document_from_snapshot(
        snapshot, jmeter_path="/opt/jmeter/bin/jmeter", jmeter_version="5.6.3"
    )

    assert list(document["scenarios"]) == [
        f"scenario_{item_ids[0]}",
        f"scenario_{item_ids[1]}",
    ]
    assert [item["scenario"] for item in document["execution"]] == list(document["scenarios"])


def test_builder_preserves_env_group_values_without_download_guard_override() -> None:
    snapshot = {
        "runType": "standard",
        "testPlan": {"runMode": "sequential"},
        "envGroup": {
            "variables": {
                "APP_MODE": "smoke",
                "base_url": "https://api.example.internal",
            }
        },
        "scenarioItems": [
            {
                "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
                "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
                "visualScenario": {"requests": []},
                "loadSettings": {
                    "concurrencyPerNode": 1,
                    "rampUpSeconds": 0,
                    "holdForSeconds": 60,
                    "iterations": None,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
        ],
        "slaRules": [],
    }

    document = build_test_plan_taurus_document_from_snapshot(
        snapshot, jmeter_path="/opt/jmeter/bin/jmeter", jmeter_version="5.6.3"
    )

    assert document["settings"]["env"] == {
        "APP_MODE": "smoke",
        "base_url": "https://api.example.internal",
    }


def test_create_test_plan_run_rolls_back_before_dedup_lookup_after_integrity_error(
    monkeypatch,
) -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    plan = SimpleNamespace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        revision=7,
        selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
    )
    actor = SimpleNamespace(id="01HZX3Y9M0E9W7Z6M5QK9S8P7D")
    new_run = SimpleNamespace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        validity=None,
    )
    existing_run = SimpleNamespace(id="01HZX3Y9M0E9W7Z6M5QK9S8P7F")

    class FakeDeleteQuery:
        def filter(self, *args):  # noqa: ANN002
            return self

        def delete(self, *, synchronize_session):  # noqa: ANN001
            return 0

    class FakeSession:
        rolled_back = False

        def scalar(self, statement):  # noqa: ANN001
            return plan

        def query(self, model):  # noqa: ANN001
            return FakeDeleteQuery()

        def add(self, item):  # noqa: ANN001
            pass

        def flush(self):
            raise IntegrityError("insert dedup", {}, Exception("duplicate dedup key"))

        def rollback(self):
            self.rolled_back = True

    db = FakeSession()
    lookup_calls = 0

    def fake_find_existing(db_arg, *, workspace_id, dedup_hash, now):  # noqa: ANN001
        nonlocal lookup_calls
        lookup_calls += 1
        if lookup_calls == 1:
            return None
        if not db_arg.rolled_back:
            raise RuntimeError("pending rollback")
        return existing_run

    monkeypatch.setattr(test_plan_services, "utc_now", lambda: now)
    monkeypatch.setattr(test_plan_services, "_rows_for_plan", lambda db_arg, *, plan_id: ([], []))
    monkeypatch.setattr(
        test_plan_services,
        "_validate_run_context",
        lambda *args, **kwargs: SimpleNamespace(expected_concurrency=1),
    )
    monkeypatch.setattr(test_plan_services, "_snapshot_payload", lambda *args, **kwargs: {})
    monkeypatch.setattr(test_plan_services, "_find_existing_dedup_run", fake_find_existing)
    monkeypatch.setattr(test_plan_services, "create_run_execution", lambda *args, **kwargs: new_run)
    monkeypatch.setattr(test_plan_services, "write_audit_event", lambda *args, **kwargs: None)

    result = test_plan_services.create_test_plan_run(
        db,
        workspace_id=plan.workspace_id,
        actor=actor,
        source_id=plan.id,
        expected_source_revision=plan.revision,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    assert result.run is existing_run
    assert result.deduplicated is True
    assert result.status_code == 200
    assert db.rolled_back is True
    assert lookup_calls == 2


def test_create_test_plan_run_rolls_back_before_dedup_lookup_after_lease_busy(
    monkeypatch,
) -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    plan = SimpleNamespace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        revision=7,
        selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
    )
    actor = SimpleNamespace(id="01HZX3Y9M0E9W7Z6M5QK9S8P7D")
    existing_run = SimpleNamespace(id="01HZX3Y9M0E9W7Z6M5QK9S8P7F")

    class FakeDeleteQuery:
        def filter(self, *args):  # noqa: ANN002
            return self

        def delete(self, *, synchronize_session):  # noqa: ANN001
            return 0

    class FakeSession:
        rolled_back = False

        def scalar(self, statement):  # noqa: ANN001
            return plan

        def query(self, model):  # noqa: ANN001
            return FakeDeleteQuery()

        def rollback(self):
            self.rolled_back = True

    db = FakeSession()
    lookup_calls = 0

    def fake_find_existing(db_arg, *, workspace_id, dedup_hash, now):  # noqa: ANN001
        nonlocal lookup_calls
        lookup_calls += 1
        if lookup_calls == 1:
            return None
        if not db_arg.rolled_back:
            raise RuntimeError("pending rollback")
        return existing_run

    def fake_create_run_execution(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AppError("LOAD_NODE_BUSY", "Load Node is busy.", 409)

    monkeypatch.setattr(test_plan_services, "utc_now", lambda: now)
    monkeypatch.setattr(test_plan_services, "_rows_for_plan", lambda db_arg, *, plan_id: ([], []))
    monkeypatch.setattr(
        test_plan_services,
        "_validate_run_context",
        lambda *args, **kwargs: SimpleNamespace(expected_concurrency=1),
    )
    monkeypatch.setattr(test_plan_services, "_snapshot_payload", lambda *args, **kwargs: {})
    monkeypatch.setattr(test_plan_services, "_find_existing_dedup_run", fake_find_existing)
    monkeypatch.setattr(test_plan_services, "create_run_execution", fake_create_run_execution)

    result = test_plan_services.create_test_plan_run(
        db,
        workspace_id=plan.workspace_id,
        actor=actor,
        source_id=plan.id,
        expected_source_revision=plan.revision,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    assert result.run is existing_run
    assert result.deduplicated is True
    assert result.status_code == 200
    assert db.rolled_back is True
    assert lookup_calls == 2
