'''Callsigns.'''
# This module was found in d-rats, but is not used by d-rats.

from __future__ import absolute_import

import ast
import re

def find_us_callsigns(string):
    '''
    Find United States Callsigns.

    :param string: Source callsigns
    :type string: str
    :returns: Strings matched
    :rtype: list of str
    '''

    extra2x1 = "[aAkKnNwW][A-z][0-9][A-z]"
    others = "[aAkKnNwW][A-z]?[0-9][A-z]{2,3}"

    regex = "\\b(%s|%s)\\b" % (extra2x1, others)

    return re.findall(regex, string)

def find_au_callsigns(string):
    '''
    Find Austrailian Callsigns.

    :param string: Source callsigns
    :type string: str
    :returns: Strings matched
    :rtype: list of str
    '''
    regex = '\\b[Vv][Kk][0-9][Ff]?[A-z]{2,3}'

    return re.findall(regex, string)

def find_ca_callsigns(string):
    '''
    Find Canadian Callsigns.

    :param string: Source callsigns
    :type string: str
    :returns: Strings matched
    :rtype: list of str
    '''
    regex = '[Vv][EeAa][0-9][A-z]{2,3}'

    return re.findall(regex, string)


CALLSIGN_FUNCTIONS = {
    "US" : find_us_callsigns,
    "Australia" : find_au_callsigns,
    "Canada" : find_ca_callsigns,
}


def find_callsigns(config, string):
    '''
    Find Callsings.

    :param config:
    :type config: :class:`DratsConfig`
    :returns: list of callsigns found
    :rtype: list of str
    '''
    call_list = []

    calls = ast.literal_eval(config.get("prefs", "callsigns"))
    enabled = [y for x, y in calls if x]

    for country in CALLSIGN_FUNCTIONS:
        if country in CALLSIGN_FUNCTIONS and country in enabled:
            call_list += CALLSIGN_FUNCTIONS[country](string)

    return call_list
