'''Map Position Module.'''
#
# Copyright 2021 John Malmberg <wb8tyw@gmail.com>
# Portions derived from works:
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2019 Maurizio Andreotti  <iz2lxi@yahoo.it>
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
from __future__ import unicode_literals

from ..gps import distance

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapPosition():
    '''
    Map Position.

    :param latitude: Latitude of position, Default 0.0
    :type latitude: float
    :param longitude: Longitude of position, Default 0.0
    :type longitude: float
    '''

    def __init__(self, latitude=0.0, longitude=0.0):
        self.latitude = latitude
        self.longitude = longitude
        self._format = "%.4f, %.4f"

    def set_format(self, format_string=None):
        '''
        Set the format string

        :param format_string: Format, default "%.4f, %.4f"
        :type format_string: str
        :returns: Formatted position
        :rtype: str
        '''
        if format_string:
            self._format = format_string

    def distance(self, position):
        '''
        Get the distance between two points.

        :param position: Second position
        :type position: :class:`Map.MapPosition`
        :returns: Distance in current units
        :rtype: float
        '''
        ret_val = distance(self.latitude, self.longitude,
                           position.latitude, position.longitude)
        return ret_val

    def __str__(self):
        return self._format % (self.latitude, self.longitude)
