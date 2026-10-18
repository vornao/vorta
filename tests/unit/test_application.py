import sys

import pytest


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS activation policy only')
def test_runs_as_accessory_app(qapp, qtbot, monkeypatch):
    """
    Without open windows a plain `vorta` run must use the bundle's LSUIElement policy, or macOS
    quits it after the last window closes. While a window is open it shows in the Dock and menu bar.
    """
    from AppKit import NSApp, NSApplicationActivationPolicyAccessory, NSApplicationActivationPolicyRegular

    main = qapp.main_window
    was_visible = main.isVisible()
    monkeypatch.setattr('vorta.views.main_window.is_system_tray_available', lambda: True)

    qapp.open_main_window_action()
    qtbot.waitUntil(lambda: NSApp.activationPolicy() == NSApplicationActivationPolicyRegular, **pytest._wait_defaults)

    main.close()
    qtbot.waitUntil(lambda: NSApp.activationPolicy() == NSApplicationActivationPolicyAccessory, **pytest._wait_defaults)

    if was_visible:
        qapp.open_main_window_action()
