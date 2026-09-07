import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import logging
import time
from datetime import timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings, validate_ssh_credential_encryption_key
from app.core.errors import AppError
from app.core.time import utc_now
from app.services.load_nodes import (
    claim_next_initialization_attempt,
    complete_initialization_attempt,
    credential_for_node,
    decrypt_credential,
    InitResult,
    LoadNodeInitializer,
    lock_active_running_attempt,
    recover_stale_initializing_nodes_without_active_attempts,
    recover_stale_running_attempts,
)
from app.services.run_control_executor import RemoteRunControlExecutor
from app.services.runs import (
    RunControlExecutionResult,
    RunControlExecutor,
    build_run_control_command,
    claim_next_run_control_request,
    cleanup_callback_retention,
    complete_run_control_request,
    recover_stale_leases,
    recover_stale_run_control_requests,
    sweep_accepted_timeouts,
    sweep_heartbeat_timeouts,
    sweep_stop_grace_timeouts,
)

logger = logging.getLogger(__name__)
LOAD_NODE_INIT_ADVISORY_LOCK = 9303
RUN_PROTOCOL_ADVISORY_LOCK = 9404


class _PrecomputedLoadNodeInitializer(LoadNodeInitializer):
    def __init__(self, result: InitResult) -> None:
        self.result = result

    def initialize(self, node, credential):  # noqa: ANN001
        _ = node, credential
        return self.result


def _default_load_node_initializer() -> LoadNodeInitializer:
    from app.services.load_node_initializer import RealLoadNodeInitializer

    return RealLoadNodeInitializer()


def _failed_initialization_result(error_code: str, log: str) -> InitResult:
    return InitResult(
        ok=False,
        log=log,
        error_code=error_code,
        message="Initialization failed.",
    )


def _try_advisory_lock(session, key: int = LOAD_NODE_INIT_ADVISORY_LOCK) -> bool:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        return bool(
            session.execute(text("select pg_try_advisory_lock(:key)"), {"key": key}).scalar()
        )
    return True


def _advisory_unlock(session, key: int = LOAD_NODE_INIT_ADVISORY_LOCK) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("select pg_advisory_unlock(:key)"), {"key": key})


@contextmanager
def _advisory_lock_section(
    session,
    key: int = LOAD_NODE_INIT_ADVISORY_LOCK,  # noqa: ANN001
) -> Iterator[bool]:
    locked = _try_advisory_lock(session, key)
    if not locked:
        # SQLAlchemy 2.x autobegins a transaction for the lock probe SELECT.
        # End it before the worker enters later explicit session.begin() blocks.
        session.rollback()
        yield False
        return
    try:
        yield True
    finally:
        _advisory_unlock(session, key)
        session.commit()


def run_once(
    session_factory: sessionmaker | None = None,
    *,
    load_node_initializer: LoadNodeInitializer | None = None,
    run_control_executor: RunControlExecutor | None = None,
) -> int:
    if session_factory is None:
        engine = create_engine(get_settings().database_url, future=True)
        session_factory = sessionmaker(
            bind=engine, autoflush=False, expire_on_commit=False, future=True
        )
    run_control_executor = run_control_executor or RemoteRunControlExecutor(
        session_factory=session_factory
    )
    completed = 0
    with session_factory() as session:
        with _advisory_lock_section(session) as locked:
            if locked:
                completed += recover_stale_running_attempts(session)
                completed += recover_stale_initializing_nodes_without_active_attempts(session)
                session.commit()
        with _advisory_lock_section(session, RUN_PROTOCOL_ADVISORY_LOCK) as locked:
            if locked:
                completed += sweep_accepted_timeouts(session)
                completed += sweep_heartbeat_timeouts(session)
                completed += sweep_stop_grace_timeouts(session)
                completed += recover_stale_run_control_requests(session)
                completed += recover_stale_leases(session)
                completed += cleanup_callback_retention(
                    session,
                    older_than=utc_now()
                    - timedelta(days=getattr(get_settings(), "runner_callback_retention_days", 30)),
                )
                session.commit()
        while True:
            with session.begin():
                attempt = claim_next_initialization_attempt(session)
            if attempt is None:
                break
            attempt_id = attempt.id
            initializer = load_node_initializer or _default_load_node_initializer()
            result: InitResult | None = None
            node = None
            credential = None
            with session.begin():
                # Reload and validate the attempt in a short transaction before setup work.
                attempt = session.get(type(attempt), attempt_id)
                if attempt is not None:
                    _active_attempt, node = lock_active_running_attempt(
                        session, attempt_id=attempt.id
                    )
                    if node is not None:
                        try:
                            credential = decrypt_credential(credential_for_node(session, node=node))
                        except AppError as exc:
                            result = _failed_initialization_result(exc.code, exc.message)
                        except Exception:
                            logger.exception(
                                "Load Node credential preparation failed",
                                extra={"attempt_id": attempt.id, "node_id": node.id},
                            )
                            result = _failed_initialization_result(
                                "LOAD_NODE_INIT_FAILED", "Unexpected setup failure."
                            )
                        session.expunge(node)
            if attempt is None or node is None:
                continue
            if result is None:
                try:
                    result = initializer.initialize(node, credential)
                except AppError as exc:
                    result = _failed_initialization_result(exc.code, exc.message)
                except Exception:
                    logger.exception(
                        "Load Node initialization failed",
                        extra={"attempt_id": attempt_id, "node_id": node.id},
                    )
                    result = _failed_initialization_result(
                        "LOAD_NODE_INIT_FAILED", "Unexpected setup failure."
                    )
            with session.begin():
                attempt = session.get(type(attempt), attempt_id)
                if attempt is not None:
                    complete_initialization_attempt(
                        session,
                        attempt=attempt,
                        initializer=_PrecomputedLoadNodeInitializer(result),
                    )
                    completed += 1
        while True:
            with session.begin():
                request = claim_next_run_control_request(session)
            if request is None:
                break
            with session.begin():
                request = session.get(type(request), request.id)
                command = (
                    build_run_control_command(session, request=request)
                    if request is not None
                    else None
                )
            if request is None:
                continue
            if command is None:
                result = RunControlExecutionResult(
                    ok=False,
                    error_code="RUN_CONTROL_TARGET_MISSING",
                    message="Run control target was not found.",
                )
            else:
                try:
                    result = run_control_executor.execute(command)
                except Exception:
                    logger.exception(
                        "Run control execution failed",
                        extra={"request_id": request.id, "action": request.action},
                    )
                    result = RunControlExecutionResult(
                        ok=False,
                        error_code="RUN_CONTROL_EXECUTION_FAILED",
                        message="Run control execution failed.",
                        quarantine_node=command is None or command.action != "start",
                        cleanup_required=command is not None and command.action == "start",
                    )
            with session.begin():
                request = session.get(type(request), request.id)
                if request is not None and request.status == "running":
                    complete_run_control_request(
                        session,
                        request=request,
                        success=result.ok,
                        error_code=result.error_code,
                        error_message=result.message,
                        stderr_preview=result.stderr_preview,
                        timed_out=result.timed_out,
                        quarantine_node=result.quarantine_node,
                        cleanup_required=result.cleanup_required,
                    )
                    completed += 1
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description="SurgePilot api-worker entrypoint.")
    parser.add_argument("--once", action="store_true", help="Run one worker cycle and exit.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    args = parser.parse_args()
    validate_ssh_credential_encryption_key()
    if args.once:
        count = run_once()
        print(f"api-worker completed {count} task(s)")
        return
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("api-worker cycle failed")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
