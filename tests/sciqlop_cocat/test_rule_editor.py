"""A smart catalogue's rule as JSON: checked by previewing it in the background, saved only when it
reads."""
import pytest

from SciQLop.components.catalogs import CatalogEvent

from .conftest import HOUR, T0


@pytest.fixture
def project(attached):
    plain = attached.create_catalog("Shocks 2019", ["r"])
    for i, tag in enumerate(["s", "s", "w"]):
        attached.add_event(plain, CatalogEvent(uuid=f"e{i}", start=T0 + i * HOUR, stop=T0 + (i + 1) * HOUR,
                                               meta={"tags": [tag]}))
    return attached, plain


def test_a_rule_with_no_text_form_is_edited_as_json(project, qtbot):
    from SciQLop.plugins.sciqlop_cocat.rule_editor import RuleEditor
    provider, _ = project
    smart = provider.create_smart_catalog("shocks", ["r"], "tag:s")
    rule = {"merge": {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}, "gap": 0}
    provider.set_catalog_search(smart, rule=rule)
    dialog = RuleEditor(provider, smart)
    qtbot.addWidget(dialog)
    assert '"merge"' in dialog.text.toPlainText()
    dialog.text.setPlainText('{"bogus": 1}')
    qtbot.waitUntil(lambda: "not a set" in dialog.problem.text(), timeout=5000)
    assert not dialog.save_button.isEnabled()
    dialog.text.setPlainText('{"filter": {"all": true}, "where": {"contains": ["tags", "w"]}}')
    qtbot.waitUntil(lambda: dialog.save_button.isEnabled(), timeout=2000)
    assert "1 event" in dialog.count.text()
    dialog.save_button.click()
    assert provider.catalog_search(smart).query == "tag:w"
