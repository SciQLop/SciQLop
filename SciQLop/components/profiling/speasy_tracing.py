"""Monkey-patches that emit `tracing.zone` events inside speasy hot spots.

speasy 1.7.x has no built-in tracing. From the SciQLop side we cannot
intercept the decorator-produced wrappers (they are baked at speasy
import time, before SciQLop runs), but every interesting call inside
those wrappers goes through one of:

  * a method looked up dynamically on a `Cacheable` / `UnversionedProviderCache`
    instance (e.g. `self._get_data_with_cache`),
  * a module-level free function referenced as a closure free variable
    (e.g. `is_proxy_up`),
  * a static method on a class (e.g. `GetProduct.get`),

so patching the class / module attribute is sufficient — the in-flight
wrapper resolves the new attribute on each call.

`install()` is idempotent and a no-op if speasy is not importable. The
zones use SciQLop's `tracing.zone` which is itself a no-op when no trace
session is active, so leaving this installed is essentially free.
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from SciQLop.core import tracing


_INSTALLED = False
_CAT = "speasy"


def _wrap_module_fn(mod, attr: str, zone_name: str,
                    arg_capture: Callable[[tuple, dict], dict] | None = None) -> None:
    fn = getattr(mod, attr, None)
    if fn is None or getattr(fn, "_sciqlop_traced", False):
        return

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        zargs = arg_capture(args, kwargs) if arg_capture else {}
        with tracing.zone(zone_name, cat=_CAT, **zargs):
            return fn(*args, **kwargs)

    wrapped._sciqlop_traced = True
    setattr(mod, attr, wrapped)


def _wrap_method(cls, attr: str, zone_name: str,
                 arg_capture: Callable[[tuple, dict], dict] | None = None) -> None:
    fn = getattr(cls, attr, None)
    if fn is None or getattr(fn, "_sciqlop_traced", False):
        return

    @functools.wraps(fn)
    def wrapped(self, *args, **kwargs):
        zargs = arg_capture(args, kwargs) if arg_capture else {}
        with tracing.zone(zone_name, cat=_CAT, **zargs):
            return fn(self, *args, **kwargs)

    wrapped._sciqlop_traced = True
    setattr(cls, attr, wrapped)


def _wrap_static(cls, attr: str, zone_name: str,
                 arg_capture: Callable[[tuple, dict], dict] | None = None) -> None:
    fn = getattr(cls, attr, None)
    if fn is None or getattr(fn, "_sciqlop_traced", False):
        return

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        zargs = arg_capture(args, kwargs) if arg_capture else {}
        with tracing.zone(zone_name, cat=_CAT, **zargs):
            return fn(*args, **kwargs)

    wrapped._sciqlop_traced = True
    setattr(cls, attr, staticmethod(wrapped))


def _safe_str(v: Any, limit: int = 96) -> str:
    try:
        s = str(v)
    except Exception:
        return "?"
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _capture_get_data(args: tuple, kwargs: dict) -> dict:
    out: dict = {}
    if "product" in kwargs:
        out["product"] = _safe_str(kwargs["product"])
    elif args:
        out["product"] = _safe_str(args[0])
    for k in ("start_time", "stop_time"):
        if k in kwargs and kwargs[k] is not None:
            out[k] = _safe_str(kwargs[k])
    return out


def _capture_url(args: tuple, kwargs: dict) -> dict:
    out: dict = {}
    url = kwargs.get("url") or (args[0] if args else None)
    if url is not None:
        out["url"] = _safe_str(url, limit=200)
    return out


def _capture_dl_variable(args: tuple, kwargs: dict) -> dict:
    out: dict = {}
    for k in ("dataset", "variable"):
        if k in kwargs and kwargs[k] is not None:
            out[k] = _safe_str(kwargs[k])
    return out


def _capture_proxy_get(args: tuple, kwargs: dict) -> dict:
    out: dict = {}
    for k in ("path", "start_time", "stop_time"):
        if k in kwargs and kwargs[k] is not None:
            out[k] = _safe_str(kwargs[k])
    return out


def _patch_cache_layer() -> None:
    from speasy.core.cache import _providers_caches as pc

    _wrap_method(pc.Cacheable, "_get_data_with_cache",
                 "speasy.cache.with_cache", _capture_get_data)
    _wrap_method(pc.Cacheable, "_get_and_wb_fragment_group",
                 "speasy.cache.fetch_fragment_group", _capture_get_data)
    _wrap_method(pc.Cacheable, "_retrieve_concurrently_requested_fragments",
                 "speasy.cache.wait_pending", _capture_get_data)
    _wrap_method(pc.UnversionedProviderCache, "_get_data_with_cache",
                 "speasy.cache.unversioned.with_cache", _capture_get_data)
    _wrap_method(pc.UnversionedProviderCache, "split_fragments",
                 "speasy.cache.unversioned.split_fragments", _capture_get_data)


def _patch_proxy_layer() -> None:
    from speasy.core import proxy as p

    _wrap_static(p.GetProduct, "get", "speasy.proxy.get_product", _capture_proxy_get)
    _wrap_static(p.GetInventory, "get", "speasy.proxy.get_inventory")
    _wrap_module_fn(p, "is_proxy_up", "speasy.proxy.is_up")
    _wrap_module_fn(p, "query_proxy_version", "speasy.proxy.version")


def _patch_http_layer() -> None:
    from speasy.core import http

    _wrap_module_fn(http, "urlopen", "speasy.http.urlopen", _capture_url)
    _wrap_module_fn(http, "is_server_up", "speasy.http.is_server_up")


def _patch_any_files_layer() -> None:
    from speasy.core import any_files

    _wrap_module_fn(any_files, "any_loc_open", "speasy.file.open", _capture_url)
    _wrap_module_fn(any_files, "_cached_get_remote_file",
                    "speasy.file.fetch_remote", _capture_url)
    _wrap_module_fn(any_files, "list_files", "speasy.file.list", _capture_url)


def _patch_codec_layer() -> None:
    from speasy.core.direct_archive_downloader import direct_archive_downloader as dad

    _wrap_module_fn(dad, "_read_cdf", "speasy.cdf.read", _capture_url)
    _wrap_module_fn(dad, "get_product", "speasy.archive.get_product")

    try:
        from speasy.core.codecs.bundled_codecs import istp_cdf as ic
    except ImportError:
        return
    for cls_name in ("IstpCdf", "CdfCodec", "ISTPCdfCodec", "IstpCdfCodec"):
        cls = getattr(ic, cls_name, None)
        if cls is not None:
            _wrap_method(cls, "load_variable", "speasy.cdf.load_variable")
            _wrap_method(cls, "load_variables", "speasy.cdf.load_variables")
            break


def _patch_cda_provider() -> None:
    try:
        from speasy.data_providers.cda import CdaWebservice
    except ImportError:
        return
    _wrap_method(CdaWebservice, "_dl_variable",
                 "speasy.cda.dl_variable", _capture_dl_variable)
    _wrap_method(CdaWebservice, "_get_data_with_direct_archive",
                 "speasy.cda.direct_archive", _capture_get_data)


def install() -> bool:
    """Install tracing patches into speasy. Idempotent. Returns True on success.

    Safe to call before/after a tracing session is active — the wrappers
    delegate to `tracing.zone` which is a no-op when tracing is disabled.
    """
    global _INSTALLED
    if _INSTALLED:
        return True
    try:
        _patch_cache_layer()
        _patch_proxy_layer()
        _patch_http_layer()
        _patch_any_files_layer()
        _patch_codec_layer()
        _patch_cda_provider()
    except ImportError:
        return False
    _INSTALLED = True
    return True


__all__ = ["install"]
