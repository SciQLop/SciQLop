"""View in Store must deep-link to the plugin's store page, not just the store."""

from pathlib import Path


WELCOME_JS = Path("SciQLop/components/welcome/resources/welcome.js")
WELCOME_BACKEND = Path("SciQLop/components/welcome/backend.py")
MAINWINDOW = Path("SciQLop/core/ui/mainwindow.py")
APPSTORE_PAGE = Path("SciQLop/components/appstore/web_appstore_page.py")
APPSTORE_JS = Path("SciQLop/components/appstore/resources/appstore.js")


def test_details_button_passes_plugin_name():
    javascript = WELCOME_JS.read_text()
    assert "escapeJsStringAttr(pkg.name)" in javascript
    assert "backend.open_appstore(\\'' + escapeJsStringAttr(pkg.name)" in javascript
    assert "backend.open_appstore()" not in javascript


def test_browse_all_opens_store_without_selection():
    javascript = WELCOME_JS.read_text()
    assert "backend.open_appstore('')" in javascript


def test_backend_forwards_plugin_name():
    backend = WELCOME_BACKEND.read_text()
    assert "appstore_requested = Signal(str)" in backend
    assert "@Slot(str)\n    def open_appstore(self, name: str" in backend
    assert "appstore_requested.emit(name" in backend


def test_mainwindow_forwards_name_to_store_page():
    mainwindow = MAINWINDOW.read_text()
    assert "def _show_appstore(self, name" in mainwindow
    assert "show_package(name)" in mainwindow


def test_store_page_selects_package_by_name():
    page = APPSTORE_PAGE.read_text()
    assert "def show_package" in page
    assert "showPackageDetailsByName" in page
    assert "loadFinished" in page


def test_store_js_selects_package_with_pending_fallback():
    javascript = APPSTORE_JS.read_text()
    assert "function showPackageDetailsByName(name)" in javascript
    assert "pendingDetailName" in javascript
    assert "showPackageDetails(found)" in javascript
