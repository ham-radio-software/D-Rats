'''Latitude and Longitude Entry Widget.'''

# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2023 John. E. Malmberg - Python3 Conversion
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .dratsexception import LatLonEntryParseDMSError
from .dratsexception import LatLonEntryValueError


class LatLonEntry(Gtk.Entry):
    '''
    Latitude Longitude Entry.

    :param args: Optional GtkEntry arguments, unused.
    :type args: tuple
    '''

    logger = logging.getLogger("LatLonEntry")

    def __init__(self, *args):
        Gtk.Entry.__init__(self, *args)

        self.connect("changed", self.format)

    @staticmethod
    def format(entry):
        '''
        Format entry text handler.

        :param entry: Entry Object
        :type entry: :class:`Gtk.Entry`
        '''
        string = entry.get_text()
        if string is None:
            return

        deg = "\u00b0"

        while " " in string:
            if "." in string:
                break
            if deg not in string:
                string = string.replace(" ", deg)
            elif "'" not in string:
                string = string.replace(" ", "'")
            elif '"' not in string:
                string = string.replace(" ", '"')
            else:
                string = string.replace(" ", "")

        entry.set_text(string)

    @staticmethod
    def parse_dd(string):
        '''
        Parse Decimal Degree string.

        :param string: text with decimal Degrees
        :type: string: str
        :returns: Numeric coordinate value
        :rtype: float
        '''
        return float(string)

    @staticmethod
    def parse_dm(string):
        '''
        Parse Degrees Minutes string.

        :param string: Text with Degrees and Minutes
        :type string: str
        :returns: Degrees and minutes
        :rtype: float
        '''
        string = string.strip()
        string = string.replace('  ', ' ')

        (_degrees, _minutes) = string.split(' ', 2)

        degrees = int(_degrees)
        minutes = float(_minutes)

        return degrees + (minutes / 60.0)

    @staticmethod
    def parse_dms(string):
        '''
        Parse Degrees Minutes Seconds from string.

        :param string: Text with Degrees Minutes and Seconds
        :type string: str
        :returns: Degrees Minutes and Seconds
        :rtype: float
        :raises: :class:`LatLonEntryParseDMSError` on parsing error.
        '''
        string = string.replace("\u00b0", " ")
        string = string.replace('"', ' ')
        string = string.replace("'", ' ')
        string = string.replace('  ', ' ')
        string = string.strip()

        items = string.split(' ')

        if len(items) > 3:
            raise LatLonEntryParseDMSError("Invalid format")
        if len(items) == 3:
            degrees_str = items[0]
            minutes_str = items[1]
            seconds_str = items[2]
        elif len(items) == 2:
            degrees_str = items[0]
            minutes_str = items[1]
            seconds_str = 0.0
        elif len(items) == 1:
            degrees_str = items[0]
            minutes_str = 0
            seconds_str = 0.0
        else:
            degrees_str = 0
            minutes_str = 0
            seconds_str = 0.0

        try:
            degrees = int(degrees_str)
        except ValueError:
            degrees = 0
            minutes_str = 0
            seconds_str = 0.0
        try:
            minutes = int(minutes_str)
        except ValueError:
            minutes = 0
            seconds_str = 0.0
        try:
            seconds = float(seconds_str)
        except ValueError:
            seconds = 0.0

        return degrees + (minutes / 60.0) + (seconds / 3600.0)

    def value(self):
        '''
        Coordinate Value.

        :returns: Coordinate value from widget
        :rtype: float
        :raises: :class:`LatLonEntryValueError` for invalid values.
        '''
        string = self.get_text()

        try:
            result = self.parse_dd(string)
            return result
        except ValueError:
            try:
                result = self.parse_dm(string)
                return result
            except ValueError:
                try:
                    result = self.parse_dms(string)
                    return result
                except LatLonEntryParseDMSError:
                    pass

        raise LatLonEntryValueError("Invalid format")

    def validate(self):
        '''
        Validate.

        :Returns: True if validates
        :rtype: bool
        '''
        try:
            self.value()
            return True
        except LatLonEntryValueError:
            return False


def test():
    '''Unit Test'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    logger = logging.getLogger("latLonEntry Test")

    window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    window.connect("destroy", Gtk.main_quit)

    lat_long_entry = LatLonEntry()
    lat_long_entry.show()
    window.add(lat_long_entry)
    window.show()

    def print_val(entry):
        if entry.validate():
            logger.info("Valid: %s", entry.value())
        else:
            logger.info("Invalid")

    lat_long_entry.connect("activate", print_val)

    lat_long_entry.set_text("45 13 12")

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    test()
