#!/usr/bin/python
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

STATUS_MAX = 9
STATUS_MIN = 0

STATUS_UNKNOWN    = 0
STATUS_ONLINE     = 1
STATUS_UNATTENDED = 2
STATUS_OFFLINE    = 9

__STATUS_MSGS = {
    STATUS_UNKNOWN    : "Unknown",
    STATUS_ONLINE     : "Online",
    STATUS_UNATTENDED : "Unattended",
    STATUS_OFFLINE    : "Offline",
}

def get_status_msgs():
    d = {}
    for k,v in __STATUS_MSGS.items():
        d[k] = _(v)
    return d

def get_status_vals():
    d = {}
    for k,v in __STATUS_MSGS.items():
        d[_(v)] = k
    return d

class Station:
    def __init__(self, callsign):
        self.__call = callsign
        self.__heard = 0
        self.__port = ""

    def set_heard(self, heard):
        self.__heard = heard

    def get_heard(self):
        return self.__heard

    def set_port(self, port):
        self.__port = port

    def get_port(self):
        return self.__port

    def __str__(self):
        return self.__call
