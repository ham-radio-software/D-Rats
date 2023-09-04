'''utility Methods.'''
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
from io import FileIO

import os
import tempfile

import urllib.request

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


def byte_ord(raw_data):
    '''
    byte to ordinal for python 2 compatibility

    :param raw_data: Byte or String character
    :type raw_data: str or bytes
    :returns: Ordinal value
    :rtype: int or bytes
    '''
    # python2 compatibility hack
    if isinstance(raw_data, str):
        return ord(raw_data)
    return raw_data


# pylint wants only 12 branches
# pylint: disable=too-many-branches
def hexprintlog(raw_data):
    '''
    Hex Print log

    :param raw_data: Data to print in HEX
    :type raw_data: str or bytes
    :returns: Checksum of data
    :rtype: int 8 bit
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
                if isinstance(char, str):
                    print(char, end='')
                else:
                    print("%s" % chr(char), end='')
            else:
                print(".", end='')

        print()

    return csum


def filter_to_ascii_bytes(bytes_str):
    '''
    Filter to ASCII bytes.

    :param byte_str: bytes string to filter
    :type byte_str: bytes
    :returns: Filtered bytes string
    :rtype: bytearray
    '''
    out_bytes = bytearray(len(bytes_str))
    idx = 0
    for byte_char in bytes_str:
        if byte_char in range(32, 127) or byte_char in [0x0a, 0x0d]:
            out_bytes[idx] = byte_char & 0xff
        idx += 1
    return out_bytes


def filter_to_ascii(string):
    '''
    Filter to ASCII.

    :param string: String to filter
    :type string: str
    :returns: Filtered string
    :rtype: str
    '''
    c_val = '\x00'
    xlate = ([c_val] * 32) + \
             [chr(x) for x in range(32, 127)] + \
             ([c_val] * 129)

    xlate[ord('\n')] = '\n'
    xlate[ord('\r')] = '\r'

    out_string = str(string).translate("".join(xlate)).replace("\x00", "")
    return out_string


def run_safe(function):
    '''
    Run function safe

    :param function: function to run
    :type function: function
    :returns: function result
    '''
    def runner(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        # pylint: disable=broad-except
        except Exception:
            logger = logging.getLogger("Utils.run_safe.runner")
            logger.info("<<<%s>>>", function, exc_info=True)
            return None

    return runner


class NetFile(FileIO):
    '''
    NetFile.

    :param uri: URI to open
    :type uri: str
    :param mode: Mode to open, default "r"
    :type mode: str
    :param buffering: Buffering level, default 1
    :type buffering: int
    '''
    logger = logging.getLogger("NetFile")

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

                self.logger.info("init: Retrieving %s -> %s", uri, self.__fn)
                urllib.request.urlretrieve(uri, self.__fn)
                break
        super().__init__(self, self.__fn, mode, buffering)

    def close(self):
        '''close'''
        super().close(self)

        if self.is_temp:
            os.remove(self.__fn)


class ExternalHash():
    '''External Hash.'''

    def __init__(self):
        self.hval = ""

    def update(self, val):
        '''
        Update.

        :param val: value to write
        :type val: bytes
        '''
        # pylint: disable=import-outside-toplevel
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
        :rtype: list[bytes]
        '''
        return self.hval.split()[0]


def combo_select(box, value):
    '''
    Combo Select.

    :param box: Box object
    :type box: :class:`Gtk.Box`
    :param value: Value to select
    :returns: True if selection is made
    :rtype: bool
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
    '''Log Exception.'''
    # pylint: disable=import-outside-toplevel
    import traceback
    import sys

    # Calls need to be integrated into logger.

    logger = logging.getLogger("Utils.log_exception")

    logger.info("-- Exception: --", exc_info=True)
    traceback.print_exc(limit=30, file=sys.stdout)
    logger.info("----------------")


def set_entry_hint(entry, hint, default_focused=False):
    '''
    Set Entry Hint.

    :param entry: Entry to show.
    :type entry: :class:`Gtk.Widget`
    :param hint: hint text
    :type hint: str
    :param default_focus: Optional make default focused
    :type default_focus: bool
    '''
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


def port_for_stationid(ports, stationid):
    '''
    Port for a Station Identification.

    :param ports: Radio port to look for a station identification in
    :type ports: dict
    :param stationid: Station identification to lookup
    :type stationid: str
    :returns: Port if found or none.
    '''
    for port, stations in ports.copy().items():
        for station in stations:
            if stationid == str(station):
                return port
    return None

# appears unused.
def make_error_dialog(msg, stack, buttons, msg_type, extra):
    '''
    Make Error Dialog

    :param stack: Stack trace text
    :type stack: str
    :param buttons: Dialog buttons
    :type buttons: :class:`Gtk.Widget`
    :param msg_type: Type of Window
    :type msg_type: :class:`Gtk,Window`
    :param extra: Extra information
    :type extra: function(:class:`Gtk.MessageDialog`)
    :returns: Result of running error dialog
    :rtype: :class:`Gtk.ResponseType`
    '''
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


# Can not find where this function is used!
def dict_rev(target_dict, key):
    '''
    Dict to lookup the key containing a value.

    Only one value is returned.

    If key is present as multiple values in target_dict, it is
    indeterminate which value will be returned.

    :param target_dict: Dict to do lookup on
    :type target_dict: dict
    :param key: value to find the key for
    :returns: Key that contains the value.
    :rtype: any
    :raises: value_error if value is not present in target_dict.
    '''
    # Alternate implementation
    reverse = {}
    for target_key, target_value in target_dict.copy().items():
        # if target_key == value:
        #    return target_key
        reverse[target_value] = target_key
    # raise value_error

    logger = logging.getLogger("Utils.dict_rev")
    logger.info("Reversed dict: %s", reverse)

    return reverse[key]
