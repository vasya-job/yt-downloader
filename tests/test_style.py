from ytgui.__main__ import create_app
from ytgui.ui.style import STYLESHEET


def test_combobox_popup_is_a_regular_dropdown():
    assert "combobox-popup: 0" in STYLESHEET


def test_app_uses_fusion_style():
    app = create_app([])
    assert app.style().objectName().lower() == "fusion"
    assert app.applicationName() == "YT Загрузчик"
