#!/usr/bin/python
'''Main Events Event Classes'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
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


class EventException(Exception):
    '''Generic Event Exception.'''


class InvalidEventType(EventException):
    '''Invalid Event Type Error.'''


class Event():
    '''
    Event.

    :param group_id: Group name
    :type group_id: str
    :param message: Event message
    :type message: str
    :param evtype: event type, Default EVENT_INFO
    :type evtype: int
    :raises: :class:`InvalidEventType` if the event type validation fails
    '''

    EVENT_INFO = 0
    EVENT_FILE_XFER = 1
    EVENT_FORM_XFER = 2
    EVENT_PING = 3
    EVENT_POS_REPORT = 4
    EVENT_SESSION = 5

    EVENT_TYPES = {EVENT_INFO : None,
                   EVENT_FILE_XFER : None,
                   EVENT_FORM_XFER : None,
                   EVENT_PING : None,
                   EVENT_POS_REPORT : None,
                   EVENT_SESSION : None
                  }


    def __init__(self, group_id, message, evtype=None):
        if not evtype:
            evtype = self.EVENT_INFO
        self.group_id = group_id

        if evtype not in self.EVENT_TYPES.keys():
            raise InvalidEventType("Invalid event type %i" % evtype)
        self.evtype = evtype
        self.message = message
        self.isfinal = False
        self.details = ""

    @classmethod
    def set_event_icon(cls, evtype, icon):
        '''
        Set Event Icon.

        :param evtype: Event type
        :type evtype: int
        :param icon: Icon for event
        :type icon: :class:`GdkPixbuf.Pixbuf`
        '''
        cls.EVENT_TYPES[evtype] = icon

    def set_as_final(self):
        '''
        Set Event as final.

        This event ends a series of events in the given group.
        '''
        self.isfinal = True

    def is_final(self):
        '''
        Is event final?

        :returns: True if the event is final
        :rtype: bool
        '''
        return self.isfinal

    def set_details(self, details):
        '''
        Set event details.

        :param details: Event details
        :type details: str
        '''
        self.details = details


class FileEvent(Event):
    '''
    File Event.

    :param group_id: Group name
    :type group_id: str
    :param message: message for event
    :type message: str
    '''
    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, self.EVENT_FILE_XFER)


class FormEvent(Event):
    '''
    Form Event.

    :param group_id: Group name
    :type group_id: str
    :param message: message for event
    :type message: str
    '''

    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, self.EVENT_FORM_XFER)


class PingEvent(Event):
    '''
    Ping Event.

    :param group_id: Group name
    :type group_id: str
    :param message: message for event
    :type message: str
    '''

    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, self.EVENT_PING)


class PosReportEvent(Event):
    '''
    Position Report Event.

    :param group_id: Group name
    :type group_id: str
    :param message: message for event
    :type message: str
    '''

    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, self.EVENT_POS_REPORT)


class SessionEvent(Event):
    '''
    Session Event.

    :param session_id: Session ID
    :type session_id: int
    :param port_id: Port Id
    :type port_id: str
    :param message: message for event
    :type message: str
    '''

    def __init__(self, session_id, port_id, message):
        group_id = "%s_%s" % (session_id, port_id)
        message = "[%s] %s" % (port_id, message)
        Event.__init__(self, group_id, message, self.EVENT_SESSION)
        self.__portid = port_id
        self.__sessionid = session_id
        self.__restart_info = None

    def get_portid(self):
        '''
        Get Port ID

        :returns: Port ID
        :rtype: str
        '''
        return self.__portid

    def get_sessionid(self):
        '''
        Get Session ID

        :returns:  Session ID
        :rtype: int
        '''
        return self.__sessionid

    def set_restart_info(self, restart_info):
        '''
        Set Restart Information.

        :param restart_info: Restart information of station, filename or None
        :type restart_info: tuple[str, str]
        '''
        self.__restart_info = restart_info

    def get_restart_info(self):
        '''
        Get Restart Information.

        :returns: Restart information tuple of station, filename or None
        :rtype: tuple[str, str]
        '''
        return self.__restart_info
