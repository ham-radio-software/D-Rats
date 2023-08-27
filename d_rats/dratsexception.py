'''Base d-rats Exception'''

#
# Copyright 2022 John Malmberg <wb8tyw@gmail.com>
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


class DataPathError(Exception):
    '''Data Path Error.'''


class DataPathNotConnectedError(DataPathError):
    '''Data Path Not Connected Error.'''


class DataPathIOError(DataPathError):
    '''Data Path IO Error'''


class LatLonEntryException(Exception):
    '''Generic LatLonEntry Exception.'''


class LatLonEntryValueError(LatLonEntryException):
    '''LatLonEntry Value Error.'''


class LatLonEntryParseDMSError(LatLonEntryException):
    '''LatLonEntry Parse DMS Error.'''


class DPRSException(Exception):
    '''Generic DPRS Exception.'''


class DPRSInvalidCode(Exception):
    '''Invalid DPRS Code.'''


class DPRSUnknownCode(Exception):
    '''Unknown DPRS Code.'''
