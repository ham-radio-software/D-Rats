'''Filename Box Class.'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

from .dplatform import Platform


class FilenameBox(Gtk.Box):
    '''
    File Name Box.

    :param mime_types: Optional Mime types to filter, default None
    :type mime_types: list[str]
    :params find_dir: Find directory, default False
    :type find_dir: bool
    :params save: File is for saving, default False
    :type save: bool
    '''
    __gsignals__ = {
        "filename-changed" : (GObject.SignalFlags.RUN_LAST,
                              GObject.TYPE_NONE, ()),
        }

    def __init__(self, mime_types=None, find_dir=False, save=True):
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=0)

        self.mime_types = mime_types

        self.save = save
        self.filename = Gtk.Entry()
        self.filename.show()
        self.pack_start(self.filename, 1, 1, 1)

        browse = Gtk.Button.new_with_label("...")
        browse.show()
        self.pack_start(browse, 0, 0, 0)

        self.filename.connect("changed", self.do_changed)
        browse.connect("clicked", self.do_browse, find_dir)

    def do_browse(self, _button, directory):
        '''
        Do Browse Button Handler.

        :param _button: Button widget
        :type _button: :class:`Gtk.Button`
        :param directory: Is a directory
        :type directory: bool
        '''
        if self.filename.get_text():
            start = os.path.dirname(self.filename.get_text())
        else:
            start = None

        platform = Platform.get_platform()
        if directory:
            fname = platform.gui_select_dir(start_dir=start)
        elif self.save:
            fname = platform.gui_save_file(mime_types=self.mime_types,
                                           start_dir=start)
        else:
            fname = platform.gui_open_file(mime_types=self.mime_types,
                                           start_dir=start)
        if fname:
            self.filename.set_text(fname)

    def do_changed(self, _dummy):
        '''
        Do Changed Handler.

        :param _dummy: Unused
        '''
        self.emit("filename_changed")

    def set_filename(self, fname):
        '''
        Set Filename.

        :param fname: File name
        :type fname: str
        '''
        self.filename.set_text(fname)

    def get_filename(self):
        '''
        Get Filename.

        :returns: Filename
        :rtype: str
        '''
        return self.filename.get_text()

    # WB8TYW: I can not find a caller of this method.
    def set_mutable(self, mutable):
        '''
        Set Mutable.

        :param mutable: Set mutable property
        :type mutable: bool
        '''
        self.filename.set_sensitive(mutable)


def test():
    '''Unit Test for FilenameBox.'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    logger = logging.getLogger("test_filenamebox")

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.connect("destroy", Gtk.main_quit)

    filename_box1 = FilenameBox(save=False)

    win.add(filename_box1)
    filename_box1.show()
    win.show()

    filename = filename_box1.get_filename()

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

    logger.info(filename)

if __name__ == "__main__":
    test()
