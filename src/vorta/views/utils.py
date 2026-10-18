import json
import os
import sys

from vorta.views.icons import has_symbol, legacy_svg_icon, symbol_icon, symbol_pixmap


def get_colored_icon(icon_name, scaled_height=128, return_qpixmap=False):
    """
    Return an icon in the colour of the current theme.

    Known icon names render as SF Symbols on macOS (bundled SVGs elsewhere) and
    follow light/dark mode automatically. Other assets, like logos, use the
    recoloured SVG.
    """
    if has_symbol(icon_name):
        if return_qpixmap:
            return symbol_pixmap(icon_name, scaled_height)
        return symbol_icon(icon_name)
    return legacy_svg_icon(icon_name, scaled_height, return_qpixmap)


def popup_menu(button, menu):
    """Show `menu` under `button`, like a pull-down button without a menu arrow."""
    menu.popup(button.mapToGlobal(button.rect().bottomLeft()))


def get_exclusion_presets():
    """
    Loads exclusion presets from JSON files in assets/exclusion_presets.

    Currently the preset name is used as identifier.
    """
    allPresets = {}
    os_tag = f"os:{sys.platform}"
    if getattr(sys, 'frozen', False):
        # we are running in a bundle
        bundle_dir = os.path.join(sys._MEIPASS, 'assets/exclusion_presets')
    else:
        # we are running in a normal Python environment
        bundle_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../assets/exclusion_presets')

    for preset_file in sorted(os.listdir(bundle_dir)):
        with open(os.path.join(bundle_dir, preset_file), 'r') as f:
            preset_list = json.load(f)
            for preset in preset_list:
                if os_tag in preset['tags']:
                    allPresets[preset['slug']] = {
                        'name': preset['name'],
                        'patterns': preset['patterns'],
                        'tags': preset['tags'],
                    }
    return allPresets
