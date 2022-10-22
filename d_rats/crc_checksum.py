'''CRC Checksum.'''
#
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


def _update_crc(c_byte, crc):
    '''
    Update the CRC.

    :param c_byte: Character byte to add
    :type c_byte: int
    :param crc: CRC to update
    :type crc: int
    :returns: 16 bit CRC
    :rtype: int
    '''
    # python 2 compatibility hack
    # :type c_byte: may be str for python2
    if isinstance(c_byte, str):
        c_byte = ord(c_byte)
    for _ in range(0, 8):
        c_byte <<= 1

        if (c_byte & 0o400) != 0:
            value = 1
        else:
            value = 0

        if crc & 0x8000:
            crc <<= 1
            crc += value
            crc ^= 0x1021
        else:
            crc <<= 1
            crc += value

    return crc & 0xFFFF


def calc_checksum(data):
    '''
    Calculate a checksum

    :param data: Data to checksum
    :type data: bytes
    :returns: checksum
    :rtype: int
    '''
    # :type data: is str for python2
    checksum = 0
    for i in data:
        checksum = _update_crc(i, checksum)

    checksum = _update_crc(0, checksum)
    checksum = _update_crc(0, checksum)
    return checksum
