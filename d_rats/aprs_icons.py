'''APRS Icons.'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2023 John Malmberg <wb8tyw@gmail.com> python3 gtk3 update
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import logging
import os

# Need Python Image Library for rendering "Numbered" ICON codes.
# If package is not present, "Numbered" ICON codes will not have
# their number code.
HAVE_PIL = False
try:
    from PIL import Image
    from PIL import ImageDraw
    # from PIL import ImageFont
    HAVE_PIL = True
except (ModuleNotFoundError, ImportError):
    pass

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GdkPixbuf
from gi.repository import GObject

from .dplatform import Platform
from .aprs_dprs import AprsDprsCodes
from .dratsexception import DPRSException
from .inputdialog import FieldDialog
from .miscwidgets import make_choice


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class APRSicons():
    '''APRS Icons.'''

    logger = logging.getLogger("APRSicons")
    ICON_MAPS = {}
    ICONS = []

    @classmethod
    def open_icon_map(cls, iconfn):
        '''
        Open icon map.

        :param iconfn: Filename with icon file
        :type iconfn: str
        :returns: Icon Map or None
        :rtype: :class:`GdkPixbuf.Pixbuf`
        '''
        if not os.path.exists(iconfn):
            cls.logger.info("Icon file %s not found", iconfn)
            return None

        try:
            return GdkPixbuf.Pixbuf.new_from_file(iconfn)
        except GLib.Error:
            cls.logger.info("open_icon_map: Error opening icon map %s",
                            iconfn, exc_info=True)
            return None

    @classmethod
    def init_icon_maps(cls):
        '''init_icon_maps.'''

        sys_data = Platform.get_platform().sys_data()
        cls.ICON_MAPS = {
            AprsDprsCodes.APRS_PRIMARY_SYMBOL_TABLE: cls.open_icon_map(
                os.path.join(sys_data, "images", "aprs_pri.png")),
            AprsDprsCodes.APRS_ALTERNATE_SYMBOL_TABLE: cls.open_icon_map(
                os.path.join(sys_data, "images", "aprs_sec.png")),
        }

    @classmethod
    def get_sub_image(cls, iconmap, h_offset, v_offset, size=20):
        '''
        Get sub image from iconmap

        :param iconmap: Icon map
        :type iconmap: :class:`GtkPixbuf.Pixbuf`
        :param h_offset: horizontal pixel offset
        :type h_offset: int
        :param v_offset: Vertical pixel offset
        :type v_offset: int
        :param size: Size of icon, default 20
        :returns: icon extracted from icon map
        :rtype: :class:`GdkPixbuf.Pixbuf`
        '''
        # Account for division lines (1px per icon)
        x_coord = (h_offset * size) + h_offset + 1
        y_coord = (v_offset * size) + v_offset + 1

        icon = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,
                                    True, 8, size, size)
        iconmap.copy_area(x_coord, y_coord, size, size, icon, 0, 0)
        return icon

    @classmethod
    def get_icon_from_map(cls, iconmap, symbol):
        '''
        Get icon from map.

        param iconmap: Pixbuf with icons for a APRS symbol table.
        :type iconmap: :class:`GdkPixbuf.Pixbuf`
        :param symbol: APRS symbol for icon
        :type symbol: str
        :returns: icon
        :rtype: :class:`GdkPixbuf.Pixbuf`
        '''
        index = ord(symbol) - ord("!")

        i = index % 16
        j = int(index / 16)

        # print ("Code `%s' is %i,%i" % (code, i, j))
        return cls.get_sub_image(iconmap, i, j)

    @classmethod
    def add_aprs_overlay(cls, pixbuf, code):
        '''
        Add Overlay to APRS pixuf

        :param pixbuf: Original Pixbuf of APRS icon
        :type pixbuf: :class:`GdkPixbuf.Pixbuf`
        :param code: APRS code
        :type code: str
        :returns: Pixbuf with optional overlay
        :rtype: :class:`GdkPixbuf.Pixbuf`
        '''
        if not HAVE_PIL or code[0] not in AprsDprsCodes.APRS_OVERLAYS:
            return pixbuf

        pixels = pixbuf.get_pixels()
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        rowstride = pixbuf.get_rowstride()
        mode = "RGB"
        has_alpha = pixbuf.get_has_alpha()
        if has_alpha:
            mode = "RGBA"
        image = Image.frombytes(mode, (width, height),
                                pixels, "raw", mode, rowstride)

        draw = ImageDraw.Draw(image)
        draw.text(xy=(int(width * 3 / 8), int(height / 4)),
                  text=code[0],fill=(0,0,0) )
        new_pixels = image.tobytes()
        display_pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(new_pixels),
            GdkPixbuf.Colorspace.RGB,
            has_alpha,
            pixbuf.get_bits_per_sample(),
            width, height,
            rowstride)
        return display_pixbuf.copy()

    @classmethod
    def get_icon(cls, code):
        '''
        Get Icon

        :param code: Text code for icon
        :type key: str
        :returns: Icon or None
        :rtype: :class:`GdkPixbuf.Pixbuf`
        '''
        if not code:
            return None

        if not cls.ICON_MAPS:
            cls.init_icon_maps()

        if len(code) == 2:
            table = code[0]
            if table in AprsDprsCodes.APRS_OVERLAYS:
                table = AprsDprsCodes.APRS_ALTERNATE_SYMBOL_TABLE
            tables = [AprsDprsCodes.APRS_PRIMARY_SYMBOL_TABLE,
                      AprsDprsCodes.APRS_ALTERNATE_SYMBOL_TABLE]
            if table not in tables:
                cls.logger.info("get_icon: Unknown APRS symbol table: %s",
                                table)
                return None

            symbol = code[1]
        elif len(code) == 1:
            table = AprsDprsCodes.APRS_PRIMARY_SYMBOL_TABLE
            symbol = code[0]
        else:
            cls.logger.info("get_icon: Unknown APRS code: `%s'", code)
            return None

        display_pixbuf = None
        try:
            pixbuf = cls.get_icon_from_map(iconmap=cls.ICON_MAPS[table],
                                           symbol=symbol)
            display_pixbuf = cls.add_aprs_overlay(pixbuf=pixbuf, code=code)
            # display_pixbuf = pixbuf
        except KeyError:
            cls.logger.info("get_icon: Error cutting icon %s",
                            code, exc_info=True)

        return display_pixbuf

    @staticmethod
    def parse_dprs_message(text=''):
        '''
        Parse out a potential DPRS message.

        This method will not validate any of the parsed data.

        If last three characters start with a '*' the last two characters
        are assumed to be a checksum.

        If this checksum is present, then first two or three characters are
        assumed to be a two character DPRS code with an optional overlay
        character, and followed by a space.

        It all of this matches, then this can be parsed into components,
        otherwise it is apparently just a text field

        :param: text: Text to parse
        :type text: str
        :returns: Dictionary of parsed components that were found.
        :rtype: dict['code':str, 'overlay':str, 'text':str, 'checksum':str]
        '''
        result = {}
        text_len = len(text)
        result['text'] = text
        if text_len > 6 and text[-3] == '*':
            # A checksum was found assume a DPRS Code
            result['checksum'] = text[-2:]
            if text[2] == ' ':
                # Two character DPRS code
                result['code'] = text[0:2]
                result['text'] = text[3:-3]
            elif text[3] == ' ':
                # Three character DPRS code
                result['code'] = text[0:2]
                result['overlay'] = text[2]
                result['text'] = text[4:-3]
            else:
                del result['checksum']
        return result

    @classmethod
    def aprs_dialog(cls, title, text=None, code=None, overlay=None):
        '''
        APRS Dialog Widget.

        This for a graphical selection of APRS codes based on
        either the base graphic symbol or the text representation.

        :param title: Title of dialog box
        :type title: str
        :param text: Default text for a text box
        :type text: str
        :param code: Default APRS code to select
        :type code: str
        :param overlay: Default overlay for APRS icon
        :type overlay: str
        :returns: APRS/DPRS message components
        :rtype: dict with optional components
        '''
        def ev_sym_changed(combo_box, oversel, icons):
            '''
            Ev Symbol changed.

            :param combo_box: Icon selection widget
            :type combo_box: :class:`Gtk.ComboBox`
            :param oversel: Overlay selection entry
            :type oversel: :class:`Gtk.ComboText`
            :param icons: List of icons
            :type icons: list:[tuple(:class:`GdkPixbuf.Pixbuf`, str)]
            '''
            # iconsel.get_active = -1 if nothing is selected.
            if combo_box.get_active() < 0:
                oversel.set_sensitive(False)
                return
            aprs_code = icons[combo_box.get_active()][1]
            if aprs_code in AprsDprsCodes.APRS_NUMBERED_ALT:
                oversel.set_sensitive(True)
            else:
                oversel.set_sensitive(False)

        cls.sort_icons()
        result={}
        dialog = FieldDialog(title=title)
        result['dialog'] = dialog
        # Text box is optional
        if text is not None:
            entry = Gtk.Entry()
            entry.set_max_length(13)
            entry.set_text(text)
            dialog.add_field(_("Message"), entry)
            result['message'] = entry

        default_code = code
        if code[0] in AprsDprsCodes.APRS_OVERLAYS:
            overlay = code[0]
            table = AprsDprsCodes.APRS_ALTERNATE_SYMBOL_TABLE
            default_code = table + code[1]
        iconsel = cls.make_pixbuf_choice(options=cls.ICONS,
                                         default=default_code)
        result['iconsel'] = iconsel
        overlaysel = make_choice(options=AprsDprsCodes.APRS_OVERLAYS + [''],
                                 editable=False, default=overlay)
        overlaysel.set_sensitive(False)
        result['overlaysel'] = overlaysel
        iconsel.connect("changed", ev_sym_changed, overlaysel, cls.ICONS)
        ev_sym_changed(iconsel, overlaysel, cls.ICONS)

        dialog.add_field(_("Icon"), iconsel)
        dialog.add_field(_("Overlay"), overlaysel)
        return result

    @classmethod
    def sort_icons(cls):
        '''Make sure icons are sorted.'''
        if cls.ICONS:
            return
        aprs_dict = AprsDprsCodes.get_aprs_to_dprs()
        for code in sorted(aprs_dict):
            icon = cls.get_icon(code=code)
            if icon:
                cls.ICONS.append((icon, code))

    @classmethod
    def aprs_selection(cls, code):
        '''
        APRS Selection Widget.

        :param code: Initial APRS code
        :type code: str
        :returns: Selected APRS code
        :type string:
        :returns: APRS code
        :rtype: string
        '''
        # Parse code into table, symbol, and overlay
        aprs_code = None
        overlay = ''
        table = code[0]
        if code in AprsDprsCodes.APRS_NUMBERED_ALT:
            table = AprsDprsCodes.APRS_ALTERNATE_SYMBOL_TABLE
            overlay = code[0]

        base_code = table + code[1]

        aprs_select = cls.aprs_dialog(title=_("APRS Symbol"),
                                      code=base_code,
                                      overlay=overlay)
        dialog = aprs_select['dialog']
        result = dialog.run()
        iconsel = aprs_select['iconsel']
        aprs_code = cls.ICONS[iconsel.get_active()][1]
        if aprs_code in AprsDprsCodes.APRS_NUMBERED_ALT:
            # A overlay is possible
            overlay = aprs_select['overlaysel'].get_active_text()
            if overlay:
                # Use the overlay code
                aprs_code = overlay + aprs_code[1]
        dialog.destroy()
        if result != Gtk.ResponseType.OK:
            return None
        return aprs_code

    @classmethod
    def dprs_selection(cls, callsign, initial=""):
        '''
        DPRS Selection Widget.

        :param callsign: Callsign for DPRS message
        :type callsign: str
        :param initial: initial string, default ""
        :type initial: str
        :returns: DPRS string with Checksum
        :rtype: str
        '''
        dprs_info = cls.parse_dprs_message(text=initial)
        def_aprs_code = AprsDprsCodes.APRS_DIGI_CODD

        if 'code' in dprs_info:
            try:
                def_aprs_code = AprsDprsCodes.dprs_to_aprs(
                    code = dprs_info['code'])
            except DPRSException:
                pass

        dprs_select = cls.aprs_dialog(title=_("DPRS message"),
                                      text=dprs_info['text'],
                                      code=def_aprs_code,
                                      overlay=dprs_info.get('overlay', ''))

        dialog = dprs_select['dialog']
        result = dialog.run()
        iconsel = dprs_select['iconsel']
        aprs_code = cls.ICONS[iconsel.get_active()][1]
        message_text = dprs_select['message'].get_text().upper()
        overlay = ''
        if aprs_code in AprsDprsCodes.APRS_NUMBERED_ALT:
            overlay = dprs_select['overlaysel'].get_active_text()
        dialog.destroy()
        if result != Gtk.ResponseType.OK:
            return None

        dprs_code = AprsDprsCodes.aprs_to_dprs(
            code=aprs_code,
            default=AprsDprsCodes.APRS_FALLBACK_CODE)

        # callsign = mainapp.get_mainapp().config.get("user", "callsign")
        string = "%s%s %s" % (dprs_code, overlay, message_text)

        check = cls.dprs_checksum(callsign=callsign, message=string)

        return string + check

    @staticmethod
    def dprs_checksum(callsign, message):
        '''
        DPRS Checksum.

        :param callsign: Station for message
        :type callsign: str
        :param message: DPRS message
        :type message: str
        :returns: Checksum String
        :rtype: str
        '''
        csum = 0
        string = "%-8s,%s" % (callsign, message)
        for i in string:
            csum ^= ord(i)
        return "*%02X" % csum

    @staticmethod
    def make_pixbuf_choice(options, default=None):
        '''
        Make Pixbuf Choice.

        :param options: Options
        :type options: list[:class:`GdkPixbuf.Pixbuf`]
        :param default: Default is None
        :type: str
        :returns: GtkBox object
        :rtype: :class:`Gtk.Box`
        '''
        store = Gtk.ListStore(GdkPixbuf.Pixbuf, GObject.TYPE_STRING)
        box = Gtk.ComboBox.new_with_model(store)

        cell = Gtk.CellRendererPixbuf()
        box.pack_start(cell, True)
        box.add_attribute(cell, "pixbuf", 0)

        cell = Gtk.CellRendererText()
        box.pack_start(cell, True)
        box.add_attribute(cell, "text", 1)

        _default = None
        for pic, value in options:
            iter_val = store.append()
            store.set(iter_val, 0, pic, 1, value)
            if default == value:
                _default = options.index((pic, value))

        if _default:
            box.set_active(_default)

        return box

def test():
    '''Unit Test'''

    dprs = APRSicons.dprs_selection(callsign="nocall",
                                    initial='NY8  MY HOME*3B')
    if dprs:
        print("DPRS Message is %s" % dprs)
    else:
        print("No DPRS code selected.")

    aprs = APRSicons.aprs_selection(code=AprsDprsCodes.APRS_ADVISORY_CODE)

    if aprs:
        print("APRS code is %s" % aprs)
    else:
        print("No APRS code selected.")

#    try:
#        Gtk.main()
#    except KeyboardInterrupt:
#        pass

if __name__ == "__main__":
    test()
