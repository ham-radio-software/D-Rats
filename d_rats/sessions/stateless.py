#!/usr/bin/python
'''Stateless.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
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
from d_rats.ddt2 import DDT2EncodedFrame
from d_rats.sessions import base


class StatelessSession(base.Session):
    '''Stateless Session.'''

    stateless = True
    type = base.T_STATELESS
    compress = True

    T_DEF = 0

    def read(self):
        '''
        Read a frame off the queue.

        :returns: Tuple of source station, destinaton station, and frame data
        '''
        frame = self.inq.dequeue()

        return frame.s_station, frame.d_station, frame.data

    # pylint: disable=arguments-differ
    def write(self, data, dest="CQCQCQ"):
        '''
        Write.

        :param data: Data to write
        :param dest: Destination station, default='CQCQCQ'
        '''
        frame = DDT2EncodedFrame()

        frame.seq = 0
        frame.type = self.T_DEF
        frame.d_station = dest
        frame.data = data

        frame.set_compress(self.compress)

        self._sm.outgoing(self, frame)
