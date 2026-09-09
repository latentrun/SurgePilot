from __future__ import annotations

import pytest

from app.core.config import get_settings


def test_runtime_bootstrap_settings_have_release_safe_defaults(monkeypatch) -> None:
    for name in (
        "LOAD_NODE_RUNTIME_ARTIFACT_DIR",
        "LOAD_NODE_RUNTIME_VERSION",
        "LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SURGEPILOT_JMETER_MEMORY_XMX", "4G")

    settings = get_settings()

    assert settings.load_node_runtime_artifact_dir == "/opt/surgepilot/runtime-artifacts"
    assert settings.load_node_runtime_version is None
    assert settings.load_node_runtime_install_timeout_seconds == 120


def test_jmeter_memory_setting_rejects_unsafe_values(monkeypatch) -> None:
    monkeypatch.setenv("SURGEPILOT_JMETER_MEMORY_XMX", "4G;rm -rf /")

    with pytest.raises(ValueError, match="SURGEPILOT_JMETER_MEMORY_XMX"):
        get_settings()
