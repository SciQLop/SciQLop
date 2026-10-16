from unittest.mock import MagicMock, patch
import pytest


class _ProductsDomain:
    name = "products"

    def snapshot(self):
        return []


@pytest.fixture(autouse=True)
def reset_facade_singleton():
    import SciQLop.components.smart_search as facade
    facade._registry = None
    yield
    facade._registry = None


@pytest.fixture
def tmp_config_dir(tmp_path):
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path)):
        yield tmp_path


@pytest.fixture(autouse=True)
def reset_initialize_state():
    yield
    import SciQLop.components.smart_search as facade
    from SciQLop.components.smart_search.settings import SmartSearchSettings
    if facade._initialized:
        SmartSearchSettings._notifier.changed.disconnect(facade._on_settings_changed)
        facade._initialized = False


def test_is_available_reflects_model2vec_importability():
    from SciQLop.components.smart_search import is_available
    assert is_available() is True  # model2vec is a mandatory dependency, always importable


def test_available_models_matches_settings_module():
    from SciQLop.components.smart_search import available_models
    from SciQLop.components.smart_search.settings import AVAILABLE_MODELS
    assert available_models() == list(AVAILABLE_MODELS)


def test_register_domain_and_query_delegate_to_registry(qtbot, monkeypatch, tmp_path):
    import SciQLop.components.smart_search as facade
    monkeypatch.setattr(facade, "_jobs_backend_instance", lambda: MagicMock())

    fake_registry = MagicMock()
    fake_registry.query.return_value = {"a": 42.0}
    monkeypatch.setattr(facade, "_get_registry", lambda: fake_registry)

    domain = _ProductsDomain()
    facade.register_domain(domain)
    facade.unregister_domain("products")
    facade.notify_changed("products")
    result = facade.query("products", "hi")

    fake_registry.register_domain.assert_called_once_with(domain)
    fake_registry.unregister_domain.assert_called_once_with("products")
    fake_registry.notify_changed.assert_called_once_with("products")
    assert result == {"a": 42.0}


def test_get_model_and_set_model_read_and_write_settings(tmp_path, monkeypatch):
    from unittest.mock import patch
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path)):
        from SciQLop.components.smart_search import get_model, set_model
        assert get_model() == "minishlab/potion-base-8M"
        set_model("minishlab/potion-base-32M")
        assert get_model() == "minishlab/potion-base-32M"


def test_set_enabled_true_persists_only_after_registry_reports_ready(tmp_config_dir, monkeypatch):
    import SciQLop.components.smart_search as facade
    from SciQLop.components.smart_search.settings import SmartSearchSettings

    def fake_set_enabled(enabled, on_ready=None, on_error=None):
        on_ready()

    fake_registry = MagicMock()
    fake_registry.set_enabled.side_effect = fake_set_enabled
    monkeypatch.setattr(facade, "_get_registry", lambda: fake_registry)

    caller_on_ready = MagicMock()
    caller_on_error = MagicMock()
    facade.set_enabled(True, on_ready=caller_on_ready, on_error=caller_on_error)

    assert SmartSearchSettings().enabled is True
    caller_on_ready.assert_called_once_with()
    caller_on_error.assert_not_called()


def test_set_enabled_true_does_not_persist_when_registry_reports_error(tmp_config_dir, monkeypatch):
    import SciQLop.components.smart_search as facade
    from SciQLop.components.smart_search.settings import SmartSearchSettings

    error = RuntimeError("model download failed")

    def fake_set_enabled(enabled, on_ready=None, on_error=None):
        on_error(error)

    fake_registry = MagicMock()
    fake_registry.set_enabled.side_effect = fake_set_enabled
    monkeypatch.setattr(facade, "_get_registry", lambda: fake_registry)

    caller_on_ready = MagicMock()
    caller_on_error = MagicMock()
    facade.set_enabled(True, on_ready=caller_on_ready, on_error=caller_on_error)

    assert SmartSearchSettings().enabled is False
    caller_on_ready.assert_not_called()
    caller_on_error.assert_called_once_with(error)


def test_set_enabled_false_persists_immediately(tmp_config_dir, monkeypatch):
    import SciQLop.components.smart_search as facade
    from SciQLop.components.smart_search.settings import SmartSearchSettings

    with SmartSearchSettings() as settings:
        settings.enabled = True

    fake_registry = MagicMock()
    monkeypatch.setattr(facade, "_get_registry", lambda: fake_registry)

    facade.set_enabled(False)

    fake_registry.set_enabled.assert_called_once_with(False, on_ready=None, on_error=None)
    assert SmartSearchSettings().enabled is False


def test_initialize_connects_notifier_and_settings_toggle_calls_set_enabled(tmp_config_dir, monkeypatch):
    import SciQLop.components.smart_search as facade
    from SciQLop.components.smart_search.settings import SmartSearchSettings

    fake_registry = MagicMock()
    fake_registry.is_enabled.return_value = False
    monkeypatch.setattr(facade, "_get_registry", lambda: fake_registry)

    facade.initialize()
    fake_registry.set_enabled.assert_not_called()

    settings = SmartSearchSettings()
    settings.enabled = True
    settings.save()

    fake_registry.set_enabled.assert_called_once()
    args, kwargs = fake_registry.set_enabled.call_args
    assert args == (True,)
    assert kwargs["on_error"] is None


def test_initialize_reentrant_persistence_write_does_not_double_call_set_enabled(tmp_config_dir, monkeypatch):
    import SciQLop.components.smart_search as facade
    from SciQLop.components.smart_search.settings import SmartSearchSettings

    enabled_state = {"value": False}
    fake_registry = MagicMock()
    fake_registry.is_enabled.side_effect = lambda: enabled_state["value"]

    def fake_set_enabled(enabled, on_ready=None, on_error=None):
        enabled_state["value"] = enabled
        if on_ready is not None:
            on_ready()

    fake_registry.set_enabled.side_effect = fake_set_enabled
    monkeypatch.setattr(facade, "_get_registry", lambda: fake_registry)

    facade.initialize()

    settings = SmartSearchSettings()
    settings.enabled = True
    settings.save()

    assert fake_registry.set_enabled.call_count == 1
    args, _ = fake_registry.set_enabled.call_args
    assert args == (True,)
    assert SmartSearchSettings().enabled is True


def test_initialize_restores_persisted_enabled_state(tmp_config_dir, monkeypatch):
    import SciQLop.components.smart_search as facade
    from SciQLop.components.smart_search.settings import SmartSearchSettings

    with SmartSearchSettings() as settings:
        settings.enabled = True

    fake_registry = MagicMock()
    fake_registry.is_enabled.return_value = False
    monkeypatch.setattr(facade, "_get_registry", lambda: fake_registry)

    facade.initialize()

    fake_registry.set_enabled.assert_called_once()
    args, _ = fake_registry.set_enabled.call_args
    assert args == (True,)


def test_get_registry_passes_index_cache_dir(monkeypatch, tmp_config_dir):
    import SciQLop.components.smart_search as facade
    monkeypatch.setattr(facade, "_jobs_backend_instance", lambda: MagicMock())
    captured = {}

    class _FakeRegistry:
        def __init__(self, jobs_backend, model_name, cache_dir, index_cache_dir):
            captured["cache_dir"] = cache_dir
            captured["index_cache_dir"] = index_cache_dir

    monkeypatch.setattr(facade, "SmartSearchRegistry", _FakeRegistry)
    facade._get_registry()

    assert captured["cache_dir"].endswith("smart_search_models")
    assert captured["index_cache_dir"].endswith("smart_search_index")
