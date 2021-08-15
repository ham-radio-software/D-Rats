#
'''utility Methods'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

from __future__ import absolute_import
from __future__ import print_function

import gettext
from io import FileIO
# import re
import os
import tempfile

# pylance can not deal with imports of six classes
import six.moves.urllib.request # type: ignore
import six.moves.urllib.parse # type: ignore
import six.moves.urllib.error # type: ignore
from six.moves import range # type: ignore

# importing printlog() wrapper
from .debug import printlog

from . import dplatform

_ = gettext.gettext


def open_icon_map(iconfn):
    '''
    Open icon map.

    :param iconfn: Filename with icon file
    :returns: Icon Map or None
    '''
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import GdkPixbuf

    if not os.path.exists(iconfn):
        printlog("Utils", "     : Icon file %s not found" % iconfn)
        return None

    try:
        return GdkPixbuf.Pixbuf.new_from_file(iconfn)
    # pylint: disable=broad-except
    except Exception as err:
        printlog("Utils",
                 "     :Error opening icon map %s: %s" % (iconfn, err))
        return None


ICON_MAPS = None


def init_icon_maps():
    '''init_icon_maps'''
    # pylint: disable=global-statement
    global ICON_MAPS

    ICON_MAPS = {
        "/" : open_icon_map(os.path.join(dplatform.get_platform().source_dir(),
                                         "images", "aprs_pri.png")),
        "\\": open_icon_map(os.path.join(dplatform.get_platform().source_dir(),
                                         "images", "aprs_sec.png")),
        }


def byte_ord(raw_data):
    '''
    byte to ordinal for python 2 compatibility

    :param raw_data: Byte or String character
    :returns: Ordinal value
    '''
    # python2 compatibility hack
    if isinstance(raw_data, str):
        return ord(raw_data)
    return raw_data


def hexprintlog(raw_data):
    '''
    Hex Print log

    :param raw_data: Data to print in HEX
    :returns: Checksum of data
    '''
    line_sz = 8
    csum = 0
    data = raw_data
    if isinstance(raw_data, bytes):
        data = bytearray(raw_data)

    lines = len(data) // line_sz

    if (len(data) % line_sz) != 0:
        lines += 1

    for i in range(0, lines):
        print("Utils", "     :%03i: " % (i * line_sz), end='')

        left = len(data) - (i * line_sz)
        if left < line_sz:
            limit = left
        else:
            limit = line_sz

        for j in range(0, limit):
            print("%02x" % byte_ord(data[(i * line_sz) + j]), end=' ')
            csum += byte_ord(data[(i * line_sz) + j])
            csum = csum & 0xFF

        if limit < line_sz:
            for j in range(0, line_sz - limit):
                print("  ", end=' ')

        print(" :", end=' ')

        for j in range(0, limit):
            char = data[(i * line_sz) + j]

            if byte_ord(char) > 0x20 and byte_ord(char) < 0x7E:
                print("%s" % chr(char), end='')
            else:
                print(".", end='')

        print()

    return csum


def filter_to_ascii(string):
    '''
    Filter To ASCII

    :param string: String to filter
    :returns: Filtered string
    '''
    c_val = '\x00'
    xlate = ([c_val] * 32) + \
             [chr(x) for x in range(32, 127)] + \
             ([c_val] * 129)

    xlate[ord('\n')] = '\n'
    xlate[ord('\r')] = '\r'

    return str(string).translate("".join(xlate)).replace("\x00", "")


def run_safe(function):
    '''
    Run function safe

    :param function: function to run
    :returns: function result
    '''
    def runner(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Utils", "     :<<<%s>>> %s" % (function, err))
            return None

    return runner


def run_gtk_locked(function):
    '''
    Run function with gtk locked.

    :param function: Function to run
    :returns: function result or raise error
    '''
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

    def runner(*args, **kwargs):
        Gdk.threads_enter()
        try:
            function(*args, **kwargs)
        # pylint: disable=broad-except
        except Exception:
            Gdk.threads_leave()
            raise

        Gdk.threads_leave()

    return runner


def run_or_error(function):
    '''
    Run Function or raise an error.

    :param function: function to run
    :returns: Function result or raise error
    '''
    # import gi
    # gi.require_version("Gtk", "3.0")
    # from gi.repository import Gtk
    from d_rats.ui import main_common

    def runner(*args, **kwargs):
        try:
            function(*args, **kwargs)
        # pylint: disable=broad-except
        except Exception as err:
            log_exception()
            main_common.display_error(_("An error occurred: ") + str(err))

    return runner


def print_stack():
    '''Print Stack'''
    import traceback
    import sys
    traceback.print_stack(file=sys.stdout)


def get_sub_image(iconmap, i, j, size=20):
    '''
    Get sub image

    :param iconmap: Icon map
    :param i: horizontal map index
    :param j: Vertical map index
    :param size: Size of icon, default 20
    :returns: icon
    '''
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import GdkPixbuf

    # Account for division lines (1px per icon)
    x_coord = (i * size) + i + 1
    y_coord = (j * size) + j + 1

    icon = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)
    iconmap.copy_area(x_coord, y_coord, size, size, icon, 0, 0)

    return icon


def get_icon_from_map(iconmap, symbol):
    '''
    Get icon from map.

    :param iconmap: Map of icons
    :param symbol: Symbol for icon
    :returns: icon
    '''
    index = ord(symbol) - ord("!")

    i = index % 16
    j = index / 16

    # print ("Symbol `%s' is %i,%i" % (symbol, i, j))

    return get_sub_image(iconmap, i, j)


def get_icon(key):
    '''
    Get Icon

    :param key: Name of icon
    :returns: Icon or None
    '''
    if not key:
        return None

    if len(key) == 2:
        if key[0] == "/":
            set_value = "/"
        elif key[0] == "\\":
            set_value = "\\"
        else:
            printlog("Utils",
                     "     :Utils     : Unknown APRS symbol table: %s" %
                     key[0])
            return None

        key = key[1]
    elif len(key) == 1:
        set_value = "/"
    else:
        printlog("Utils", "     :Utils     : Unknown APRS symbol: `%s'" % key)
        return None

    try:
        return get_icon_from_map(ICON_MAPS[set_value], key)
    # pylint: disable=broad-except
    except Exception as err:
        printlog("Utils", "     :Error cutting icon %s: %s" % (key, err))
        return None


class NetFile(FileIO):
    '''NetFile'''

    def __init__(self, uri, mode="r", buffering=1):
        self.__fn = uri
        self.is_temp = False

        methods = ["http", "https", "ftp"]
        for method in methods:
            if uri.startswith("%s://" % method):
                self.is_temp = True
                tmpf = tempfile.NamedTemporaryFile()
                self.__fn = tmpf.name
                tmpf.close()

                printlog("Utils",
                         "     :Retrieving %s -> %s" % (uri, self.__fn))
                six.moves.urllib.request.urlretrieve(uri, self.__fn)
                break

        super(NetFile, self).__init__(self, self.__fn, mode, buffering)

    def close(self):
        '''close'''
        super(NetFile, self).close(self)

        if self.is_temp:
            os.remove(self.__fn)


class ExternalHash():
    '''External Hash'''

    def __init__(self):
        self.hval = ""

    def update(self, val):
        '''
        Update

        :param val: value to write
        '''
        from subprocess import Popen, PIPE
        proc = Popen("md5sum", shell=True,
                     stdin=PIPE, stdout=PIPE, close_fds=True)
        proc.stdin.write(val)
        proc.stdin.close()

        self.hval = proc.stdout.read()
        proc.stdout.close()

    def digest(self):
        '''
        Digest

        :returns: List of values.
        '''
        return self.hval.split()[0]


def combo_select(box, value):
    '''
    Combo Select

    :param box: Box object
    :param value: Value to select
    :returns: True if selection is made
    '''
    store = box.get_model()
    item_iter = store.get_iter_first()
    while item_iter:
        if store.get(item_iter, 0)[0] == value:
            box.set_active_iter(item_iter)
            return True
        item_iter = store.iter_next(item_iter)

    return False


def log_exception():
    '''Log Exception'''
    import traceback
    import sys

    printlog("Utils", "     :-- Exception: --")
    traceback.print_exc(limit=30, file=sys.stdout)
    printlog("Utils", "     :------")


def set_entry_hint(entry, hint, default_focused=False):
    '''
    Set Entry Hint.

    :param entry: Entry to show.
    :param hint: hint text
    :default_focus: Optional make default focused
    '''
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    from gi.repository import Gdk

    def focus(entry, _event, direction):
        if direction == "out" and not entry.get_text():
            entry.set_text(hint)
            color = Gdk.color_parse("grey")
        elif direction == "in" and entry.get_text() == hint:
            entry.set_text("")
            color = Gdk.color_parse("black")
        else:
            return
        # modify_text deprecated in GTK 3.0 says to use override_color
        # override_color deprecated in GTK 3.16 says to use a custom
        # style provider and style classes instead.
        entry.modify_text(Gtk.StateType.NORMAL, color)

    entry.connect("focus-in-event", focus, "in")
    entry.connect("focus-out-event", focus, "out")

    if not default_focused:
        focus(entry, None, "out")


def port_for_station(ports, station):
    '''
    Port for station

    :param ports: Port to look for a station in
    :param station: Station callsign to lookup
    :returns: Port if found or none.
    '''
    for port, stations in ports.items():
        if station in stations:
            return port
    return None


def make_error_dialog(msg, stack, buttons, msg_type, extra):
    '''
    Make Error Dialog

    :param stack: Stack trace text
    :param buttons: Dialog buttons
    :param msg_type: Type of message
    :param extra: Extra information
    :returns: Result of running error dialog
    '''
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    dialog = Gtk.MessageDialog(buttons=buttons, type=msg_type)

    if extra:
        extra(dialog)

    dvbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 3)

    scroll_view = Gtk.TextView()
    scroll_view.get_buffer().set_text(stack)

    dvbox.pack_start(scroll_view, 1, 1, 1)
    scroll_view.show()

    s_expander = Gtk.Expander.new(_("Details"))
    s_expander.add(dvbox)
    dvbox.show()

    dialog.vbox.pack_start(s_expander, 1, 1, 1)
    s_expander.show()

    dialog.set_markup(msg)
    result = dialog.run()
    dialog.destroy()

    return result


def dict_rev(target_dict, key):
    '''
    Dict to lookup the key containing a value.

    if value is not unique to a key, only one key will be returned
    :param target_dict: Dict to do lookup on.
    :param key: value to find the key for.
    :returns: Key that contains the value.
    '''
    reverse = {}
    for key, value in target_dict.items():
        reverse[value] = key

    printlog("Utils", "     :Reversed dict: %s" % reverse)

    return reverse[key]
