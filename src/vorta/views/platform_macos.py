"""
Native macOS integration for the GUI layer.

Everything that talks to AppKit lives here, so the rest of the views can stay
plain Qt. Every entry point degrades to a no-op (or ``None``) when not running on
macOS, or when AppKit refuses, so Linux and odd macOS versions keep working.
"""

import logging
import sys
from typing import Optional

from PyQt6.QtCore import QByteArray, QRect, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

IS_MACOS = sys.platform == 'darwin'

_APP_WINDOW_TYPES = (Qt.WindowType.Window,)

if IS_MACOS:
    try:
        import AppKit
        import objc
    except ImportError:  # pragma: no cover - pyobjc is a hard dependency on macOS
        IS_MACOS = False


def _ns_color(color: QColor):
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(
        color.redF(), color.greenF(), color.blueF(), color.alphaF()
    )


def sf_symbol_image(name: str, point_size: float, scale: float = 2.0, weight: str = 'regular') -> Optional[QImage]:
    """
    Render an SF Symbol as a black template image with alpha.

    Returns ``None`` if the symbol doesn't exist on this system (or not on macOS),
    so callers can fall back to a bundled SVG.
    """
    if not IS_MACOS:
        return None
    try:
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
        if image is None:
            return None
        weights = {
            'regular': AppKit.NSFontWeightRegular,
            'medium': AppKit.NSFontWeightMedium,
            'semibold': AppKit.NSFontWeightSemibold,
        }
        config = AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(
            point_size, weights.get(weight, AppKit.NSFontWeightRegular), AppKit.NSImageSymbolScaleMedium
        )
        image = image.imageWithSymbolConfiguration_(config)
        size = image.size()
        width, height = max(1, round(size.width * scale)), max(1, round(size.height * scale))
        rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(  # noqa: E501
            None, width, height, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0
        )
        rep.setSize_(size)
        AppKit.NSGraphicsContext.saveGraphicsState()
        try:
            AppKit.NSGraphicsContext.setCurrentContext_(
                AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
            )
            image.drawInRect_(AppKit.NSMakeRect(0, 0, size.width, size.height))
        finally:
            AppKit.NSGraphicsContext.restoreGraphicsState()
        data = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, None)
        qimage = QImage.fromData(QByteArray(bytes(data)))
        if qimage.isNull():
            return None
        qimage.setDevicePixelRatio(scale)
        return qimage
    except Exception:  # pragma: no cover - AppKit edge cases
        logger.debug('Could not render SF Symbol %s', name, exc_info=True)
        return None


def native_windows_available() -> bool:
    """True when Qt windows are backed by NSWindows (not e.g. the offscreen platform)."""
    from PyQt6.QtGui import QGuiApplication

    return IS_MACOS and QGuiApplication.platformName() == 'cocoa'


def reduce_transparency() -> bool:
    if not IS_MACOS:
        return True
    try:
        return bool(AppKit.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceTransparency())
    except Exception:  # pragma: no cover
        return True


def update_app_presence() -> None:
    """
    Be a regular app (Dock icon, menu bar) while any Vorta window is visible, and an
    accessory app otherwise. A plain `vorta` run that stays regular without windows is
    quit by macOS shortly after its last window closes.
    """
    from PyQt6.QtWidgets import QApplication

    visible = any(
        w.isVisible() and w.isWindow() and w.windowType() in _APP_WINDOW_TYPES for w in QApplication.topLevelWidgets()
    )
    set_regular_app(visible)


def set_regular_app(regular: bool) -> None:
    """
    Show (regular) or hide (accessory) the Dock icon and menu bar.

    Vorta lives in the menu bar. While its main window is open it behaves like a
    normal app, so it gets a Dock icon, a menu bar and shows up in the app switcher.
    """
    if not native_windows_available():
        return
    try:
        policy = (
            AppKit.NSApplicationActivationPolicyRegular if regular else AppKit.NSApplicationActivationPolicyAccessory
        )
        app = AppKit.NSApplication.sharedApplication()
        if app.activationPolicy() != policy:
            app.setActivationPolicy_(policy)
    except Exception:  # pragma: no cover
        logger.debug('Could not change activation policy', exc_info=True)


class WindowChrome:
    """
    Gives a Qt window the macOS 26+ look:

    - content extends under a transparent, title-less titlebar,
    - an empty unified toolbar so the traffic lights sit in a tall toolbar area,
    - a floating Liquid Glass sidebar (vibrancy material on older systems).

    The Qt window must use ``WA_TranslucentBackground`` and
    ``NoTitleBarBackgroundHint``; Qt keeps painting everything except the
    sidebar area, which shows the native glass views placed behind it.
    """

    SIDEBAR_INSET = 8
    SIDEBAR_RADIUS = 18

    def __init__(self, widget: QWidget):
        self.widget = widget
        self.installed = False
        self._backdrop = None
        self._glass = None
        self._ns_view = None

    def install(self) -> bool:
        if not native_windows_available() or self.installed:
            return self.installed
        try:
            ns_view = objc.objc_object(c_void_p=int(self.widget.winId()))
            ns_window = ns_view.window()
            frame_view = ns_view.superview()
            if ns_window is None or frame_view is None:
                return False

            ns_window.setStyleMask_(ns_window.styleMask() | AppKit.NSWindowStyleMaskFullSizeContentView)
            ns_window.setTitlebarAppearsTransparent_(True)
            ns_window.setTitleVisibility_(AppKit.NSWindowTitleHidden)
            if ns_window.toolbar() is None:
                toolbar = AppKit.NSToolbar.alloc().initWithIdentifier_('com.borgbase.vorta.main')
                toolbar.setShowsBaselineSeparator_(False)
                ns_window.setToolbar_(toolbar)
            ns_window.setToolbarStyle_(AppKit.NSWindowToolbarStyleUnified)
            ns_window.setTitlebarSeparatorStyle_(AppKit.NSTitlebarSeparatorStyleNone)

            bounds = frame_view.bounds()
            backdrop = AppKit.NSBox.alloc().initWithFrame_(bounds)
            backdrop.setBoxType_(AppKit.NSBoxCustom)
            backdrop.setBorderWidth_(0)
            backdrop.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)

            glass_cls = getattr(AppKit, 'NSGlassEffectView', None)
            if glass_cls is not None:
                glass = glass_cls.alloc().initWithFrame_(AppKit.NSZeroRect)
                glass.setCornerRadius_(self.SIDEBAR_RADIUS)
            else:
                glass = AppKit.NSVisualEffectView.alloc().initWithFrame_(AppKit.NSZeroRect)
                glass.setMaterial_(AppKit.NSVisualEffectMaterialSidebar)
                glass.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
                glass.setState_(AppKit.NSVisualEffectStateFollowsWindowActiveState)
            glass.setAutoresizingMask_(AppKit.NSViewHeightSizable)

            frame_view.addSubview_positioned_relativeTo_(glass, AppKit.NSWindowBelow, ns_view)
            frame_view.addSubview_positioned_relativeTo_(backdrop, AppKit.NSWindowBelow, glass)
            self._backdrop, self._glass, self._ns_view = backdrop, glass, ns_view
            self.installed = True
            return True
        except Exception:
            logger.warning('Could not install native window chrome', exc_info=True)
            self.remove()
            return False

    def ensure(self) -> None:
        """Re-apply the window style if Qt reset it (it rewrites the style mask in some code paths)."""
        if not self.installed or self._ns_view is None:
            return
        try:
            ns_window = self._ns_view.window()
            if ns_window is None:
                return
            if not ns_window.styleMask() & AppKit.NSWindowStyleMaskFullSizeContentView:
                ns_window.setStyleMask_(ns_window.styleMask() | AppKit.NSWindowStyleMaskFullSizeContentView)
            if not ns_window.titlebarAppearsTransparent():
                ns_window.setTitlebarAppearsTransparent_(True)
        except Exception:  # pragma: no cover
            logger.debug('Could not re-apply window chrome', exc_info=True)

    def remove(self) -> None:
        for view in (self._glass, self._backdrop):
            if view is not None:
                try:
                    view.removeFromSuperview()
                except Exception:  # pragma: no cover
                    pass
        self._backdrop = self._glass = self._ns_view = None
        self.installed = False

    def set_background(self, color: QColor) -> None:
        if self._backdrop is not None:
            self._backdrop.setFillColor_(_ns_color(color))

    def set_sidebar_rect(self, rect: Optional[QRect]) -> None:
        """Place the glass under ``rect`` (window coordinates), or hide it for ``None``."""
        if self._glass is None:
            return
        if rect is None or rect.isEmpty():
            self._glass.setHidden_(True)
            return
        height = self._ns_view.bounds().size.height
        inset = self.SIDEBAR_INSET
        self._glass.setHidden_(False)
        self._glass.setFrame_(
            AppKit.NSMakeRect(
                rect.x() + inset,
                height - rect.y() - rect.height() + inset,
                rect.width() - 2 * inset,
                rect.height() - 2 * inset,
            )
        )
