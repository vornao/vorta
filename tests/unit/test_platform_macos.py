import sys

import pytest

from vorta.views import platform_macos

pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='macOS only')


def test_click_count_guard(qapp):
    """Reading clickCount of a non-mouse event (Qt's tray icon does this on macOS 27) must not raise."""
    from AppKit import (
        NSEvent,
        NSEventTypeApplicationDefined,
        NSEventTypeLeftMouseDown,
        NSMakePoint,
    )

    assert platform_macos.install_click_count_guard()

    other = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
        NSEventTypeApplicationDefined, NSMakePoint(0, 0), 0, 0, 0, None, 7, 1, 1
    )
    assert other.clickCount() == 0

    mouse = NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(  # noqa: E501
        NSEventTypeLeftMouseDown, NSMakePoint(0, 0), 0, 0, 0, None, 0, 2, 1.0
    )
    assert mouse.clickCount() == 2
