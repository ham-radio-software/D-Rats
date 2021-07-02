'''Sniff Packets'''
from __future__ import absolute_import
import struct

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject

from d_rats.sessions import control, stateless

# pylint: disable=invalid-name
session_types = {
    4 : "General",
    5 : "File",
    6 : "Form",
    7 : "Socket",
    8 : "PFile",
    9 : "PForm",
}


class SniffSession(stateless.StatelessSession, GObject.GObject):
    '''
    Sniff Session.

    :param a: arguments
    :param k: key word arguments
    '''
    __gsignals__ = {
        "incoming_frame" : (GObject.SIGNAL_RUN_LAST,
                            GObject.TYPE_NONE,
                            (GObject.TYPE_STRING,    # Src
                             GObject.TYPE_STRING,    # Dst
                             GObject.TYPE_STRING,    # Summary
                             ))
        }

    def __init__(self, *a, **k):
        stateless.StatelessSession.__init__(self, *a, **k)
        GObject.GObject.__init__(self)

        self.handler = self._handler

    # pylint: disable=no-self-use
    def decode_control(self, frame):
        '''
        Decode Control information from frame.

        :param frame: Frame data
        :returns: Decoded frame data
        '''
        if frame.type == control.T_ACK:
            local_session, remote_session = struct.unpack("BB", frame.data)
            return _("Control: ACK") + " " + \
                _("Local") + ":%i " % local_session + \
                _("Remote") + ":%i" % remote_session
        if frame.type == control.T_END:
            return _("Control: END session %s") % frame.data
        if frame.type >= control.T_NEW:
            ident = frame.data[0]
            name = frame.data[1:]
            stype = session_types.get(frame.type,
                                      "Unknown type %i" % frame.type)
            return _("Control: NEW session") +" %i: '%s' (%s)" % \
                     (ident, name, stype)
        return _("Control: UNKNOWN")

    def _handler(self, frame):
        hdr = "%s->%s" % (frame.s_station, frame.d_station)

        if frame.s_station == "!":
            # Warm-up frame
            return

        if frame.session == 1:
            msg = "(%s: %s)" % (_("chat"), frame.data)
        elif frame.session == 0:
            msg = self.decode_control(frame)
        else:
            msg = "(S:%i L:%i)" % (frame.session, len(frame.data))

        self.emit("incoming_frame",
                  frame.s_station, frame.d_station,
                  "%s %s" % (hdr, msg))
