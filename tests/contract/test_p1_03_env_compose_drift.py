from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p1_03_base_compose_does_not_make_web_runtime_or_secret_settings_authoritative() -> None:
    compose = (ROOT / "infra/docker/docker-compose.base.yml").read_text()
    assert "VITE_API_BASE_URL" not in compose
    assert "RUNNER_INTERNAL_TOKEN: change-me" not in compose
    assert "MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}" in compose
    assert "MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-minioadmin}" in compose


def test_p1_03_governance_docs_record_env_and_compose_drift_rules() -> None:
    sdd = (ROOT / "docs/sdd/slices/P1-03-workspace-admin.md").read_text()
    assert ".env.example" in sdd
    assert "no Web runtime `VITE_API_BASE_URL` environment override" in sdd
    assert "Monitoring/Grafana/Influx secrets remain outside System Settings" in sdd
