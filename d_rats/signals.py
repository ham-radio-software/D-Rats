#!/usr/bin/python
'''D-Rats Signals.'''
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
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject

STATUS = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,))

USER_STOP_SESSION = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,         # Session ID
      GObject.TYPE_STRING))     # Port Name

USER_CANCEL_SESSION = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,         # Session ID
      GObject.TYPE_STRING))     # Port Name

USER_SEND_FORM = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,      # Station
      GObject.TYPE_STRING,      # Port Name
      GObject.TYPE_STRING,      # Filename
      GObject.TYPE_STRING))     # Session name
RPC_SEND_FORM = USER_SEND_FORM

USER_SEND_FILE = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,      # Station
      GObject.TYPE_STRING,      # Port Name
      GObject.TYPE_STRING,      # Filename
      GObject.TYPE_STRING))     # Session name
RPC_SEND_FILE = USER_SEND_FILE

USER_SEND_CHAT = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,      # Station
      GObject.TYPE_STRING,      # Port Name
      GObject.TYPE_STRING,      # Text
      GObject.TYPE_BOOLEAN))    # Raw

INCOMING_CHAT_MESSAGE = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,      # Source
      GObject.TYPE_STRING,      # Destination
      GObject.TYPE_STRING))     # Text
OUTGOING_CHAT_MESSAGE = INCOMING_CHAT_MESSAGE

GET_STATION_LIST = \
    (GObject.SignalFlags.ACTION, GObject.TYPE_PYOBJECT,
     ())

GET_MESSAGE_LIST = \
    (GObject.SignalFlags.ACTION, GObject.TYPE_PYOBJECT,
     (GObject.TYPE_STRING,))    # Station

SUBMIT_RPC_JOB = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_PYOBJECT,    # Job
      GObject.TYPE_STRING))     # Port Name

EVENT = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_PYOBJECT,))  # Event

NOTICE = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     ())

CONFIG_CHANGED = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     ())

SHOW_MAP_STATION = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,))     # Station

PING_STATION = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,       # Station
      GObject.TYPE_STRING))      # Port Name

PING_STATION_ECHO = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,       # Station
      GObject.TYPE_STRING,       # Port Name
      GObject.TYPE_STRING,       # Data
      GObject.TYPE_PYOBJECT,     # Callback
      GObject.TYPE_PYOBJECT))    # Callback data

PING_REQUEST = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,       # Source
      GObject.TYPE_STRING,       # Destination
      GObject.TYPE_STRING))      # Data
PING_RESPONSE = PING_REQUEST

INCOMING_GPS_FIX = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_PYOBJECT,))   # Fix

STATION_STATUS = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,       # Station,
      GObject.TYPE_INT,          # Status,
      GObject.TYPE_STRING))      # Status message

GET_CURRENT_STATUS = \
    (GObject.SignalFlags.ACTION, GObject.TYPE_PYOBJECT,
     ())

GET_CURRENT_POSITION = \
    (GObject.SignalFlags.ACTION, GObject.TYPE_PYOBJECT,
     (GObject.TYPE_STRING,))     # Station (None for self)

SESSION_STARTED = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,          # Session ID
      GObject.TYPE_STRING))      # Type

SESSION_ENDED = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,          # Session ID
      GObject.TYPE_STRING,       # Message,
      GObject.TYPE_PYOBJECT))    # Restart info

SESSION_STATUS_UPDATE = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,          # Session ID
      GObject.TYPE_STRING))      # Message

FILE_RECEIVED = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,          # Session ID
      GObject.TYPE_STRING))      # Filename

FORM_RECEIVED = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,          # Session ID
      GObject.TYPE_STRING))      # Filename

FILE_SENT = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,          # Session ID
      GObject.TYPE_STRING))      # Filename

FORM_SENT = \
    (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
     (GObject.TYPE_INT,          # Session ID
      GObject.TYPE_STRING))      # Filename

GET_CHAT_PORT = \
    (GObject.SignalFlags.ACTION, GObject.TYPE_STRING,
     ())

TRIGGER_MSG_ROUTER = \
    (GObject.SignalFlags.ACTION, GObject.TYPE_NONE,
     (GObject.TYPE_STRING,))     # account (section) to trigger, "" if msgrouter

REGISTER_OBJECT = \
    (GObject.SignalFlags.ACTION, GObject.TYPE_NONE,
     (GObject.TYPE_PYOBJECT,))   # Object to register
