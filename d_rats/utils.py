#
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

#importing printlog() wrapper
from .debug import printlog

from io import FileIO
import re
import os
import tempfile
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error


from . import dplatform
from six.moves import range

def open_icon_map(iconfn):
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import GdkPixbuf

    if not os.path.exists(iconfn):
        printlog("Utils","     : Icon file %s not found" % iconfn)
        return None
    
    try:
        return GdkPixbuf.Pixbuf.new_from_file(iconfn)
    except Exception as e:
        printlog("Utils","     :Error opening icon map %s: %s" % (iconfn, e))
        return None

ICON_MAPS = None

def init_icon_maps():
    global ICON_MAPS

    ICON_MAPS = {
        "/" : open_icon_map(os.path.join(dplatform.get_platform().source_dir(),
                                         "images", "aprs_pri.png")),
        "\\": open_icon_map(os.path.join(dplatform.get_platform().source_dir(),
                                         "images", "aprs_sec.png")),
        }

def byte_ord(raw_data):
    # python2 compatibility hack
    if isinstance(raw_data, str):
        return ord(raw_data)
    return raw_data

def hexprintlog(raw_data):
    line_sz = 8
    csum = 0
    data = raw_data
    if isinstance(raw_data, bytes):
        data = bytearray(raw_data)

    lines = len(data) // line_sz
    
    if (len(data) % line_sz) != 0:
        lines += 1

    for i in range(0, lines):
        print("Utils","     :%03i: " % (i * line_sz), end='')

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
                print("  ", end = ' ')

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
        c = '\x00'
        xlate = ([c] * 32) + \
                [chr(x) for x in range(32,127)] + \
                ([c] * 129)

        xlate[ord('\n')] = '\n'
        xlate[ord('\r')] = '\r'

        return str(string).translate("".join(xlate)).replace("\x00", "")

def run_safe(f):
    def runner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            printlog("Utils","     :<<<%s>>> %s" % (f, e))
            return None

    return runner

def run_gtk_locked(f):
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

    def runner(*args, **kwargs):
        Gdk.threads_enter()
        try:
            f(*args, **kwargs)
        except Exception:
            Gdk.threads_leave()
            raise

        Gdk.threads_leave()

    return runner

def run_or_error(f):
    # import gi
    # gi.require_version("Gtk", "3.0")
    # from gi.repository import Gtk
    # from d_rats.ui import main_common

    def runner(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except Exception as e:
            log_exception()
            main_common.display_error(_("An error occurred: ") + str(e))

    return runner

def print_stack():
    import traceback, sys
    traceback.print_stack(file=sys.stdout)

def get_sub_image(iconmap, i, j, size=20):
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    from gi.repository import GdkPixbuf

    # Account for division lines (1px per icon)
    x = (i * size) + i + 1
    y = (j * size) + j + 1

    icon = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)
    iconmap.copy_area(x, y, size, size, icon, 0, 0)
    
    return icon

def get_icon_from_map(iconmap, symbol):
    index = ord(symbol) - ord("!")

    i = index % 16
    j = index / 16

    # print ("Symbol `%s' is %i,%i" % (symbol, i, j))

    return get_sub_image(iconmap, i, j)

def get_icon(key):
    if not key:
        return None

    if len(key) == 2:
        if key[0] == "/":
            set = "/"
        elif key[0] == "\\":
            set = "\\"
        else:
            printlog("Utils","     :Utils     : Unknown APRS symbol table: %s" % key[0])
            return None

        key = key[1]
    elif len(key) == 1:
        set = "/"
    else:
        printlog("Utils","     :Utils     : Unknown APRS symbol: `%s'" % key)
        return None

    try:
        return get_icon_from_map(ICON_MAPS[set], key)
    except Exception as e:
        printlog("Utils","     :Error cutting icon %s: %s" % (key, e))
        return None

class NetFile(FileIO):
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

                printlog("Utils","     :Retrieving %s -> %s" % (uri, self.__fn))
                six.moves.urllib.request.urlretrieve(uri, self.__fn)
                break
        
        super(NetFile, self).__init__(self, self.__fn, mode, buffering)

    def close(self):
        super(NetFile, self).close(self)

        if self.is_temp:
            os.remove(self.__fn)

class ExternalHash(object):
    def __init__(self):
        self.hval = ""

    def update(self, val):
        import popen2
        stdout, stdin = popen2.popen2("md5sum")
        stdin.write(val)
        stdin.close()

        self.hval = stdout.read()
        stdout.close()

    def digest(self):
        return self.hval.split()[0]

def combo_select(box, value):
    store = box.get_model()
    iter = store.get_iter_first()
    while iter:
        if store.get(iter, 0)[0] == value:
            box.set_active_iter(iter)
            return True
        iter = store.iter_next(iter)

    return False

def log_exception():
        import traceback
        import sys

        printlog("Utils","     :-- Exception: --")
        traceback.print_exc(limit=30, file=sys.stdout)
        printlog("Utils","     :------")

def set_entry_hint(entry, hint, default_focused=False):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    from gi.repository import Gdk

    def focus(entry, event, direction):
        if direction == "out" and not entry.get_text():
            entry.set_text(hint)
            c = Gdk.color_parse("grey")
        elif direction == "in" and entry.get_text() == hint:
            entry.set_text("")
            c = Gdk.color_parse("black")
        else:
            return
        entry.modify_text(Gtk.StateType.NORMAL, c)
        
    entry.connect("focus-in-event", focus, "in")
    entry.connect("focus-out-event", focus, "out")

    if not default_focused:
        focus(entry, None, "out")

def port_for_station(ports, station):
    for port, stations in ports.items():
        if station in stations:
            return port
    return None

def make_error_dialog(msg, stack, buttons, type, extra):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    d = Gtk.MessageDialog(buttons=buttons, type=type)

    if extra:
        extra(d)

    dvbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 3)

    sv = Gtk.TextView()
    sv.get_buffer().set_text(stack)

    dvbox.pack_start(sv, 1, 1, 1)
    sv.show()

    se = Gtk.Expander.new(_("Details"))
    se.add(dvbox)
    dvbox.show()

    d.vbox.pack_start(se, 1, 1, 1)
    se.show()

    d.set_markup(msg)
    r = d.run()
    d.destroy()

    return r

def dict_rev(target_dict, key):
    reverse = {}
    for k,v in target_dict.items():
        reverse[v] = k

    printlog("Utils","     :Reversed dict: %s" % reverse)

    return reverse[key]
