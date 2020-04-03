#!/usr/bin/python
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

import gobject

STATUS = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,))

USER_STOP_SESSION = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,         # Session ID
      gobject.TYPE_STRING))     # Port Name

USER_CANCEL_SESSION = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,         # Session ID
      gobject.TYPE_STRING))     # Port Name

USER_SEND_FORM = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,      # Station
      gobject.TYPE_STRING,      # Port Name
      gobject.TYPE_STRING,      # Filename
      gobject.TYPE_STRING))     # Session name
RPC_SEND_FORM = USER_SEND_FORM

USER_SEND_FILE = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,      # Station
      gobject.TYPE_STRING,      # Port Name
      gobject.TYPE_STRING,      # Filename
      gobject.TYPE_STRING))     # Session name
RPC_SEND_FILE = USER_SEND_FILE

USER_SEND_CHAT = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,      # Station
      gobject.TYPE_STRING,      # Port Name
      gobject.TYPE_STRING,      # Text
      gobject.TYPE_BOOLEAN))    # Raw

INCOMING_CHAT_MESSAGE = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,      # Source
      gobject.TYPE_STRING,      # Destination
      gobject.TYPE_STRING))     # Text
OUTGOING_CHAT_MESSAGE = INCOMING_CHAT_MESSAGE

GET_STATION_LIST = \
    (gobject.SIGNAL_ACTION, gobject.TYPE_PYOBJECT,
     ())

GET_MESSAGE_LIST = \
    (gobject.SIGNAL_ACTION, gobject.TYPE_PYOBJECT,
     (gobject.TYPE_STRING,))    # Station

SUBMIT_RPC_JOB = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_PYOBJECT,    # Job
      gobject.TYPE_STRING))     # Port Name

EVENT = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_PYOBJECT,))  # Event

NOTICE = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     ())

CONFIG_CHANGED = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     ())

SHOW_MAP_STATION = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,))     # Station

PING_STATION = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,       # Station
      gobject.TYPE_STRING))      # Port Name

PING_STATION_ECHO = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,       # Station
      gobject.TYPE_STRING,       # Port Name
      gobject.TYPE_STRING,       # Data
      gobject.TYPE_PYOBJECT,     # Callback
      gobject.TYPE_PYOBJECT))    # Callback data

PING_REQUEST = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,       # Source
      gobject.TYPE_STRING,       # Destination
      gobject.TYPE_STRING))      # Data
PING_RESPONSE = PING_REQUEST

INCOMING_GPS_FIX = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_PYOBJECT,))   # Fix

STATION_STATUS = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,       # Station,
      gobject.TYPE_INT,          # Status,
      gobject.TYPE_STRING))      # Status message

GET_CURRENT_STATUS = \
    (gobject.SIGNAL_ACTION, gobject.TYPE_PYOBJECT,
     ())

GET_CURRENT_POSITION = \
    (gobject.SIGNAL_ACTION, gobject.TYPE_PYOBJECT,
     (gobject.TYPE_STRING,))     # Station (None for self)

SESSION_STARTED = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,          # Session ID
      gobject.TYPE_STRING))      # Type

SESSION_ENDED = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,          # Session ID
      gobject.TYPE_STRING,       # Message,
      gobject.TYPE_PYOBJECT))    # Restart info

SESSION_STATUS_UPDATE = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,          # Session ID
      gobject.TYPE_STRING))      # Message

FILE_RECEIVED = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,          # Session ID
      gobject.TYPE_STRING))      # Filename

FORM_RECEIVED = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,          # Session ID
      gobject.TYPE_STRING))      # Filename

FILE_SENT = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,          # Session ID
      gobject.TYPE_STRING))      # Filename

FORM_SENT = \
    (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
     (gobject.TYPE_INT,          # Session ID
      gobject.TYPE_STRING))      # Filename

GET_CHAT_PORT = \
    (gobject.SIGNAL_ACTION, gobject.TYPE_STRING,
     ())

TRIGGER_MSG_ROUTER = \
    (gobject.SIGNAL_ACTION, gobject.TYPE_NONE,
     (gobject.TYPE_STRING,))     # account (section) to trigger, "" if msgrouter

REGISTER_OBJECT = \
    (gobject.SIGNAL_ACTION, gobject.TYPE_NONE,
     (gobject.TYPE_PYOBJECT,))   # Object to register
