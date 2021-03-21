
from __future__ import absolute_import
import struct

import gobject

from d_rats.sessions import base, control, stateless

session_types = {
    4 : "General",
    5 : "File",
    6 : "Form",
    7 : "Socket",
    8 : "PFile",
    9 : "PForm",
}

class SniffSession(stateless.StatelessSession, gobject.GObject):
    __gsignals__ = {
        "incoming_frame" : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE,
                            (gobject.TYPE_STRING,    # Src
                             gobject.TYPE_STRING,    # Dst
                             gobject.TYPE_STRING,    # Summary
                             ))
        }

    def __init__(self, *a, **k):
        stateless.StatelessSession.__init__(self, *a, **k)
        gobject.GObject.__init__(self)

        self.handler = self._handler

    def decode_control(self, frame):
        if frame.type == control.T_ACK:
            l, r = struct.unpack("BB", frame.data)
            return _("Control: ACK") + " " + \
                _("Local") + ":%i " % l + \
                _("Remote") + ":%i" % r
        elif frame.type == control.T_END:
            return _("Control: END session %s") % frame.data
        elif frame.type >= control.T_NEW:
            ident = frame.data[0]
            name = frame.data[1:]
            stype = session_types.get(frame.type,
                                      "Unknown type %i" % frame.type)
            return _("Control: NEW session") + " %i: '%s' (%s)" % \
                     (ident, name, stype)
        else:
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


