"""Public facade for the smart-search component. Wraps a lazily-constructed
SmartSearchRegistry singleton -- see docs/superpowers/specs/
2026-07-17-smart-search-component-design.md."""
from SciQLop.components.smart_search.domain import SEARCH_DOMAINS, SearchDomain
from SciQLop.components.smart_search.registry import SmartSearchRegistry
from SciQLop.components.smart_search.settings import AVAILABLE_MODELS, SmartSearchSettings
from SciQLop.core.extensions import current_owner
from SciQLop.user_api.threading import on_main_thread

_registry = None
_initialized = False


def _jobs_backend_instance():
    from SciQLop.components.jobs.backend.jobs_backend import jobs_backend_instance
    return jobs_backend_instance()


def _cache_dir() -> str:
    from platformdirs import user_cache_dir
    return user_cache_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True) + "/smart_search_models"


def _index_cache_dir() -> str:
    from platformdirs import user_cache_dir
    return user_cache_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True) + "/smart_search_index"


def _get_registry() -> SmartSearchRegistry:
    global _registry
    if _registry is None:
        with SmartSearchSettings() as settings:
            model_name = settings.model
        _registry = SmartSearchRegistry(
            _jobs_backend_instance(), model_name=model_name, cache_dir=_cache_dir(),
            index_cache_dir=_index_cache_dir())
        for domain in SEARCH_DOMAINS.list():
            _registry.register_domain(domain)
    return _registry


def register_domain(domain: SearchDomain) -> None:
    """From any thread; the owner is the caller's, captured before the call moves to the main thread."""
    _contribute_domain(domain, current_owner())


@on_main_thread
def _contribute_domain(domain: SearchDomain, owner: str) -> None:
    SEARCH_DOMAINS.contribute(domain, owner=owner)


@on_main_thread
def unregister_domain(name: str) -> None:
    if name in SEARCH_DOMAINS:
        SEARCH_DOMAINS.remove(name)


def _on_domain_added(domain: SearchDomain) -> None:
    _get_registry().register_domain(domain)


def _on_domain_removed(domain: SearchDomain) -> None:
    _get_registry().unregister_domain(domain.name)


# Plain functions, not a registry's bound methods: tests replace the lazily built registry.
SEARCH_DOMAINS.signals.added.connect(_on_domain_added)
SEARCH_DOMAINS.signals.removed.connect(_on_domain_removed)


def notify_changed(domain_name: str) -> None:
    _get_registry().notify_changed(domain_name)


def query(domain_name: str, text: str) -> dict:
    return _get_registry().query(domain_name, text)


def is_available() -> bool:
    try:
        import model2vec  # noqa: F401
    except ImportError:
        return False
    return True


def is_enabled() -> bool:
    return _get_registry().is_enabled()


def set_enabled(enabled: bool, on_ready=None, on_error=None) -> None:
    if not enabled:
        _get_registry().set_enabled(False, on_ready=on_ready, on_error=on_error)
        with SmartSearchSettings() as settings:
            settings.enabled = False
        return

    def _persist_then_ready() -> None:
        with SmartSearchSettings() as settings:
            settings.enabled = True
        if on_ready is not None:
            on_ready()

    _get_registry().set_enabled(True, on_ready=_persist_then_ready, on_error=on_error)


def available_models() -> list:
    return list(AVAILABLE_MODELS)


def get_model() -> str:
    with SmartSearchSettings() as settings:
        return settings.model


def set_model(name: str) -> None:
    if name not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown smart-search model: {name!r}. Available: {AVAILABLE_MODELS}")
    with SmartSearchSettings() as settings:
        settings.model = name


def _on_settings_changed(field_name: str, value) -> None:
    if field_name != "enabled":
        return
    if bool(value) == is_enabled():
        return
    set_enabled(bool(value))


def initialize() -> None:
    """Call once at startup: restores persisted enable state and reacts to
    future Settings UI toggles. The is_enabled()-equality guard in
    _on_settings_changed prevents a reentrant loop: set_enabled()'s own
    internal persistence write (settings.enabled = enabled, once the async
    enable job resolves) re-fires this same signal, but by then the
    registry's is_enabled() already matches, so the guard stops it there.

    Idempotent: a second call is a no-op, so it's safe even if startup code
    were to run this more than once (and avoids double-connecting the
    shared, process-lifetime _notifier)."""
    global _initialized
    if _initialized:
        return
    _initialized = True
    SmartSearchSettings._notifier.changed.connect(_on_settings_changed)
    with SmartSearchSettings() as settings:
        if settings.enabled:
            set_enabled(True)
