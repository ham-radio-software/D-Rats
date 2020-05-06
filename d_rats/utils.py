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
import re
import os
import tempfile
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error

from . import dplatform
from six.moves import range

def open_icon_map(iconfn):
    import gtk

    if not os.path.exists(iconfn):
        print("Icon file %s not found" % iconfn)
        return None
    
    try:
        return gtk.gdk.pixbuf_new_from_file(iconfn)
    except Exception as e:
        print("Error opening icon map %s: %s" % (iconfn, e))
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

def hexprint(data):
    col = 0

    line_sz = 8
    csum = 0

    lines = len(data) / line_sz
    
    if (len(data) % line_sz) != 0:
        lines += 1
        data += "\x00" * ((lines * line_sz) - len(data))
        
    for i in range(0, (len(data)/line_sz)):


        print("%03i: " % (i * line_sz), end=' ')

        left = len(data) - (i * line_sz)
        if left < line_sz:
            limit = left
        else:
            limit = line_sz
            
        for j in range(0,limit):
            print("%02x " % ord(data[(i * line_sz) + j]), end=' ')
            csum += ord(data[(i * line_sz) + j])
            csum = csum & 0xFF

        print("  ", end=' ')

        for j in range(0,limit):
            char = data[(i * line_sz) + j]

            if ord(char) > 0x20 and ord(char) < 0x7E:
                print("%s" % char, end=' ')
            else:
                print(".", end=' ')

        print("")

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
            print("<<<%s>>> %s" % (f, e))
            return None

    return runner

def run_gtk_locked(f):
    import gtk

    def runner(*args, **kwargs):
        gtk.gdk.threads_enter()
        try:
            f(*args, **kwargs)
        except Exception as e:
            gtk.gdk.threads_leave()
            raise

        gtk.gdk.threads_leave()

    return runner

def run_or_error(f):
    import gtk
    from d_rats.ui import main_common

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
    import gtk

    # Account for division lines (1px per icon)
    x = (i * size) + i + 1
    y = (j * size) + j + 1

    icon = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, 1, 8, size, size)
    iconmap.copy_area(x, y, size, size, icon, 0, 0)
    
    return icon

def get_icon_from_map(iconmap, symbol):
    index = ord(symbol) - ord("!")

    i = index % 16
    j = index / 16

    #print "Symbol `%s' is %i,%i" % (symbol, i, j)

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
            print("Unknown APRS symbol table: %s" % key[0])
            return None

        key = key[1]
    elif len(key) == 1:
        set = "/"
    else:
        print("Unknown APRS symbol: `%s'" % key)
        return None

    try:
        return get_icon_from_map(ICON_MAPS[set], key)
    except Exception as e:
        print("Error cutting icon %s: %s" % (key, e))
        return None

class NetFile(file):
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

                print("Retrieving %s -> %s" % (uri, self.__fn))
                six.moves.urllib.request.urlretrieve(uri, self.__fn)
                break
        
        file.__init__(self, self.__fn, mode, buffering)

    def close(self):
        file.close(self)

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

        print("-- Exception: --")
        traceback.print_exc(limit=30, file=sys.stdout)
        print("------")

def set_entry_hint(entry, hint, default_focused=False):
    import gtk

    def focus(entry, event, direction):
        if direction == "out" and not entry.get_text():
            entry.set_text(hint)
            c = gtk.gdk.color_parse("grey")
        elif direction == "in" and entry.get_text() == hint:
            entry.set_text("")
            c = gtk.gdk.color_parse("black")
        else:
            return
        entry.modify_text(gtk.STATE_NORMAL, c)
        
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
    import gtk
    d = gtk.MessageDialog(buttons=buttons, type=type)

    if extra:
        extra(d)

    dvbox = gtk.VBox(False, 3)

    sv = gtk.TextView()
    sv.get_buffer().set_text(stack)

    dvbox.pack_start(sv, 1, 1, 1)
    sv.show()

    se = gtk.Expander(_("Details"))
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

    print("Reversed dict: %s" % reverse)

    return reverse[key]
