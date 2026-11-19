"""FastAPI dependencies. The run manager is one per process (tests replace it with dependency_overrides)."""
from apps.api import config
from apps.api.services.run_manager import RunManager

_manager: RunManager | None = None


def get_run_manager() -> RunManager:
    global _manager
    if _manager is None:
        store = None
        if config.run_events_store_enabled():            # the timeline of every run is written to the table run_events (migration 017)
            from apps.api.services.run_event_store import RunEventStore
            store = RunEventStore()
        _manager = RunManager(event_store=store)
    return _manager


def shutdown_run_manager() -> None:
    global _manager
    if _manager is not None:
        _manager.shutdown()
        _manager = None
