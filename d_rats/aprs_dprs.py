'''DPRS and APRS Module.'''
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Python3 update Copyright 2023 John Malmberg <wb8tyw@qsl.net>
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

from .dratsexception import DPRSInvalidCode
from .dratsexception import DPRSUnknownCode

class AprsDprsCodes:
    '''
    Operations on DPRS and APRS Codes.

    This uses class methods to initialize global lookup tables, and static
    methods to look up the translations.

    `DPRS information <http://www.aprs.net/vm/DOS/SYMBOLS.HTM>`
    '''

    APRS_PRIMARY_SYMBOL_TABLE = '/'
    APRS_ALTERNATE_SYMBOL_TABLE = '\\'
    APRS_CAR_CODE = '/>'
    APRS_DIGI_CODD = '/#'
    APRS_DOT_CODE = '//'
    APRS_FALLBACK_CODE = '//'
    APRS_INFO_KIOSK_CODE = '\\?'
    APRS_NUMBERED_AIRCRAFT_CODE = '\\^'
    APRS_NUMBERED_BOX_CODE= '\\A'
    APRS_NUMBERED_CAR_CODE = '\\>'
    APRS_NUMBERED_CIRCLE_CODE = '\\0'
    APRS_NUMBERED_DIAMOND_CODE = '\\&'
    APRS_NUMBERED_SHIP_CODE = '\\#'
    APRS_NUMBERED_STAR_CODE = '\\s'
    APRS_NUMBERED_TRIANGLE_CODE = '\\n'
    APRS_NUMBERED_TRUCK_CODE = '\\u'
    APRS_NUMBERED_VAN_CODE = '\\v'
    APRS_WEATHER_CODE = '/_'

    numerals = [chr (x) for x in range(ord('0'), ord('9') + 1)]
    letters = [chr (x) for x in range(ord("A"), ord("Z") + 1) ] + \
              ['!', '?', '*']
    APRS_OVERLAYS = numerals + letters

    APRS_NUMBERED_ALT = [APRS_NUMBERED_AIRCRAFT_CODE,
                         APRS_NUMBERED_BOX_CODE,
                         APRS_NUMBERED_CAR_CODE,
                         APRS_NUMBERED_CIRCLE_CODE,
                         APRS_NUMBERED_DIAMOND_CODE,
                         APRS_NUMBERED_STAR_CODE,
                         APRS_NUMBERED_SHIP_CODE,
                         APRS_NUMBERED_TRIANGLE_CODE,
                         APRS_NUMBERED_TRUCK_CODE,
                         APRS_NUMBERED_VAN_CODE
                         ]

    _dprs_to_aprs = {}
    _aprs_to_dprs = {}

    logger = logging.getLogger("dprs_gprs")

    @classmethod
    def _init_dprs_to_aprs(cls):
        '''
        Initialize DPRS_TO_APRS data.

        The DPRS to APRS mapping is pretty horrific, this module attempts
        to create a mapping based on looking at the javascript for DPRSCalc
        and a list of regular APRS symbols

        `DPRS information <https://www.aprs-is.net/DPRS.aspx>`_
        `DPRS Caldulator <http://www.aprs-is.net/DPRSCalc.aspx>_
        '''

        if cls._dprs_to_aprs:
            return
        for indx in range(0, 26):
            asciival = ord("A") + indx
            char = chr(asciival)

            pri = cls.APRS_PRIMARY_SYMBOL_TABLE
            sec = cls.APRS_ALTERNATE_SYMBOL_TABLE

            cls._dprs_to_aprs["P%s" % char] = pri + char
            cls._dprs_to_aprs["L%s" % char] = pri + char.lower()
            cls._dprs_to_aprs["A%s" % char] = sec + char
            cls._dprs_to_aprs["S%s" % char] = sec + char.lower()

            if indx <= 15:
                pchar = chr(ord(" ") + indx)
                cls._dprs_to_aprs["B%s" % char] = pri + pchar
                cls._dprs_to_aprs["O%s" % char] = sec + pchar
            elif indx >= 17:
                pchar = chr(ord(" ") + indx + 9)
                cls._dprs_to_aprs["M%s" % char] = pri + pchar
                cls._dprs_to_aprs["N%s" % char] = sec + pchar

            if indx <= 5:
                char = chr(ord("S") + indx)
                pchar = chr(ord("[") + indx)
                cls._dprs_to_aprs["H%s" % char] = pri + pchar
                cls._dprs_to_aprs["D%s" % char] = sec + pchar

    @classmethod
    def _init_aprs_to_dprs(cls):
        '''Initialize APRS to DPRS data.'''
        if cls._aprs_to_dprs:
            return
        cls._init_dprs_to_aprs()
        for key, value in cls._dprs_to_aprs.items():
            cls._aprs_to_dprs[value] = key

    @classmethod
    def dprs_to_aprs(cls, code, default=None):
        '''
        DPRS to APRS.

        Lookup APRS code from DPRS code.

        :param symbol: Text starting with DPRS code
        :type symbol: str
        :param default: Backup APRS code if symbol not found
        :type default: str
        :returns: APRS code
        :rtype: str
        :raises: `dratsexecption.DPRSException` if DPRS symbol not found
        '''
        cls._init_dprs_to_aprs()
        aprs_code = None
        code_len = len(code)
        if code_len < 2:
            raise DPRSInvalidCode("Invalid DPRS symbol code len %i" % code_len)
        aprs_code = cls._dprs_to_aprs.get(code[0:2], default)
        if not aprs_code:
            raise DPRSUnknownCode("Unknown DPRS code '%s'" % code)

        # Handle the three character DPRS symbols
        if aprs_code in cls.APRS_NUMBERED_ALT:
            if code_len >= 3 and code[2] in cls.APRS_OVERLAYS:
                aprs_code = code[2] + aprs_code[1]
        return aprs_code

    @classmethod
    def aprs_to_dprs(cls, code, default=None):
        '''
        APRS to DPRS.

        Lookup DPRS code from APRS code.
        Fall back to the default code if the given APRS code does not exist.

        :param symbol: APRS table and code
        :type symbol: str
        :param default: Backup APRS code if code not found.
        :type default: str
        :returns: DPRS code
        :rtype: str
        '''
        cls._init_aprs_to_dprs()
        aprs_code = code[0:2]
        if len(aprs_code) < 2:
            # hack to avoid array out of bound exceptions
            aprs_code='  '
        overlay = None
        if aprs_code[0] in cls.APRS_OVERLAYS:
            base_symbol = cls.APRS_ALTERNATE_SYMBOL_TABLE + code[1]
            if base_symbol in cls.APRS_NUMBERED_ALT:
                aprs_code = base_symbol
                overlay = code[0]
        code_list = [aprs_code, default, cls.APRS_FALLBACK_CODE]
        if not default:
            default = cls.APRS_FALLBACK_CODE
        for test_code in code_list:
            if test_code in cls._aprs_to_dprs:
                break
        dprs_code = cls._aprs_to_dprs[test_code]
        # Handle 3 character DPRS codes
        if overlay:
            dprs_code = dprs_code + overlay
        return dprs_code

    @classmethod
    def get_aprs_to_dprs(cls):
        '''
        Get aprs_to_dprs dictionary.

        :returns: Populated DPRS dictionary
        :type: dict
        '''
        # python no longer allows classmethod and property to be
        # used together so we need a get class method.
        cls._init_aprs_to_dprs()
        return cls._aprs_to_dprs


def main():
    '''Unit Test.'''

    my_dict = AprsDprsCodes.get_aprs_to_dprs()
    for aprs_code in my_dict:
        dprs_code = AprsDprsCodes.aprs_to_dprs(aprs_code)
        check_code = AprsDprsCodes.dprs_to_aprs(dprs_code)
        print("APRS %s Check %s DPRS %s" %
              (aprs_code, check_code, dprs_code))


if __name__ == "__main__":
    main()
