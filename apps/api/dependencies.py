"""FastAPI dependencies. The run manager is one per process (tests replace it with dependency_overrides)."""
from apps.api.services.run_manager import RunManager

_manager: RunManager | None = None


def get_run_manager() -> RunManager:
    global _manager
    if _manager is None:
        _manager = RunManager()
    return _manager


def shutdown_run_manager() -> None:
    global _manager
    if _manager is not None:
        _manager.shutdown()
        _manager = None
