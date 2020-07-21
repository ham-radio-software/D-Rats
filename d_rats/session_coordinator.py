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

from __future__ import absolute_import
from __future__ import print_function

#importing print() wrapper
from .debug import printlog

import socket
import threading
import time
import os

import gobject

from . import formgui
from . import emailgw
from . import signals
from . import msgrouting
from .utils import run_safe, run_gtk_locked

from d_rats.sessions import base, file, form, sock

class SessionThread(object):
    OUTGOING = False

    def __init__(self, coord, session, data):
        self.enabled = True
        self.coord = coord
        self.session = session
        self.arg = data

        self.thread = threading.Thread(target=self.worker, args=(data,))
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        self.enabled = False
        self.thread.join()

    def worker(self, **args):
        printlog("SessCoord"," : **** EMPTY SESSION THREAD ****")

class FileBaseThread(SessionThread):
    progress_key = "recv_size"

    @run_safe
    def status_cb(self, vals):
        #print "GUI Status:"
        #for k,v in vals.items():
        #    print "   -> %s: %s" % (k, v)

        if vals["total_size"]:
            pct = (float(vals[self.progress_key]) / vals["total_size"]) * 100.0
        else:
            pct = 0.0

        if vals["retries"] > 0:
            retries = " (%i retries)" % vals["retries"]
        else:
            retries = ""

        if "start_time" in vals:
            elapsed = time.time() - vals["start_time"]
            kbytes = vals[self.progress_key]
            speed = " %2.2f B/s" % (kbytes / elapsed)
        else:
            speed = ""

        if vals["sent_wire"]:
            amt = vals["sent_wire"]
            if amt > 1024:
                sent = " (%s %.1f KB)" % (_("Total"), amt >> 10)
            else:
                sent = " (%s %i B)" % (_("Total"), amt)
        else:
            sent = ""

        msg = "%s [%02.0f%%]%s%s%s" % (vals["msg"], pct, speed, sent, retries)

        self.pct_complete = pct

        self.coord.session_status(self.session, msg)

    def completed(self, objname=None):
        self.coord.session_status(self.session, _("Transfer Completed"))

        if objname:
            msg = " of %s" % objname
        else:
            msg = ""

        size = self.session.stats["total_size"]
        if size > 1024:
            size >>= 10
            units = "KB"
        else:
            units = "B"

        if "start_time" in self.session.stats:
            start = self.session.stats["start_time"]
            exmsg = " (%i%s @ %2.2f B/s)" % (\
                size, units,
                self.session.stats["total_size"] /
                (time.time() - start))
        else:
            exmsg = ""

    def failed(self, restart_info=None):
        s = _("Transfer Interrupted") + \
            " (%.0f%% complete)" % self.pct_complete

        self.coord.session_failed(self.session, s, restart_info)

    def __init__(self, *args):
        SessionThread.__init__(self, *args)

        self.pct_complete = 0.0

        self.session.status_cb = self.status_cb

class FileRecvThread(FileBaseThread):
    progress_key = "recv_size"
    
    def worker(self, path):
        fn = self.session.recv_file(path)
        if fn:
            self.completed("file %s" % os.path.basename(fn))
            self.coord.session_newfile(self.session, fn)
        else:
            self.failed()

class FileSendThread(FileBaseThread):
    OUTGOING = True
    progress_key = "sent_size"

    def worker(self, path):
        if self.session.send_file(path):
            self.completed("file %s" % os.path.basename(path))
            self.coord.session_file_sent(self.session, path)
        else:
            self.failed((self.session.get_station(), path))

class FormRecvThread(FileBaseThread):
    progress_key = "recv_size"

    def worker(self, path):
        md = os.path.join(self.coord.config.form_store_dir(), _("Inbox"))
        newfn = time.strftime(os.path.join(md, "form_%m%d%Y_%H%M%S.xml"))
        if not msgrouting.msg_lock(newfn):
            printlog("SessCoord : AIEE! Unable to lock incoming new message file!")

        fn = self.session.recv_file(newfn)

        name = "%s %s %s" % (self.session.name,
                               _("from"),
                               self.session.get_station())

        if fn == newfn:
            form = formgui.FormFile(fn)
            form.add_path_element(self.coord.config.get("user", "callsign"))
            form.save_to(fn)

            self.completed("form")
            self.coord.session_newform(self.session, fn)
        else:
            self.failed()
            printlog("SessCoord"," : <--- Form transfer failed -->")

class FormSendThread(FileBaseThread):
    OUTGOING = True
    progress_key = "sent_size"

    def worker(self, path):
        if self.session.send_file(path):
            self.completed()
            self.coord.session_form_sent(self.session, path)
        else:
            self.failed((self.session.get_station(), path))

class SocketThread(SessionThread):
    def status(self):
        vals = self.session.stats

        if vals["retries"] > 0:
            retries = " (%i %s)" % (vals["retries"], _("retries"))
        else:
            retries = ""


        msg = "%i %s %s %i %s %s%s" % (vals["sent_size"],
                                       _("bytes"), _("sent"),
                                       vals["recv_size"],
                                       _("bytes"), _("received"),
                                       retries)
        self.coord.session_status(self.session, msg)

    def socket_read(self, sock, length, to=5):
        data = ""
        t = time.time()

        while (time.time() - t) < to :
            d = ""

            try:
                d = sock.recv(length - len(d))
            except socket.timeout:
                continue

            if not d and not data:
                raise Exception("Socket is closed")

            data += d

        return data

    def worker(self, data):
        (sock, timeout) = data

        printlog(("SessCoord : *** Socket thread alive (%i timeout)" % timeout))

        sock.settimeout(timeout)

        while self.enabled:
            t = time.time()
            try:
                sd = self.socket_read(sock, 512, timeout)
            except Exception as e:
                printlog(("SessCoord : %s " % str(e)))
                break
            printlog("SessCoord"," : Waited %f sec for socket" % (time.time() - t))
            
            try:
                rd = self.session.read(512)
            except base.SessionClosedError as e:
                printlog("SessCoord"," : Session closed")
                self.enabled = False
                break

            self.status()

            if sd:
                printlog("SessCoord"," : Sending socket data (%i)" % len(sd))
                self.session.write(sd)

            if rd:
                printlog("SessCoord"," : Sending radio data (%i)" % len(rd))
                sock.sendall(rd)
        
        printlog("SessCoord"," : Closing session")

        self.session.close()
        try:
            sock.close()
        except:
            pass

        printlog("SessCoord"," : *** Socket thread exiting")
                




class SessionCoordinator(gobject.GObject):
    __gsignals__ = {
        "session-status-update" : signals.SESSION_STATUS_UPDATE,
        "session-started" : signals.SESSION_STARTED,
        "session-ended" : signals.SESSION_ENDED,
        "file-received" : signals.FILE_RECEIVED,
        "form-received" : signals.FORM_RECEIVED,
        "file-sent" : signals.FILE_SENT,
        "form-sent" : signals.FORM_SENT,
        }

    _signals = __gsignals__

    def _emit(self, signal, *args):
        gobject.idle_add(self.emit, signal, *args)

    def session_status(self, session, msg):
        self._emit("session-status-update", session._id, msg)

    def session_newform(self, session, path):
        self._emit("form-received", session._id, path)

    def session_newfile(self, session, path):
        self._emit("file-received", session._id, path)

    def session_form_sent(self, session, path):
        self._emit("form-sent", session._id, path)

    def session_file_sent(self, session, path):
        self._emit("file-sent", session._id, path)

    def session_failed(self, session, msg, restart_info=None):
        self._emit("session-ended", session._id, msg, restart_info)

    def cancel_session(self, id, force=False):
        if id < 2:
            # Don't let them cancel Control or Chat
            return

        try:
            session = self.sm.sessions[id]
        except Exception as e:
            printlog("SessCoord"," : Session `%i' not found: %s" % (id, e))
            return        

        if id in self.sthreads:
            del self.sthreads[id]
        session.close(force)

    def create_socket_listener(self, sport, dport, dest):
        if dport not in list(self.socket_listeners.keys()):
            printlog("SessCoord"," : Starting a listener for port %i->%s:%i" % (sport, dest, dport))
            self.socket_listeners[dport] = \
                sock.SocketListener(self.sm, dest, sport, dport)
            printlog("SessCoord"," : Started")
        else:
            raise Exception("Listener for %i already active" % dport)

    def new_file_xfer(self, session, direction):
        msg = _("File transfer of %s started with %s") % (session.name,
                                                          session._st)
        self.emit("session-status-update", session._id, msg)

        if direction == "in":
            dd = self.config.get("prefs", "download_dir")
            self.sthreads[session._id] = FileRecvThread(self, session, dd)
        elif direction == "out":
            of = self.outgoing_files.pop()
            self.sthreads[session._id] = FileSendThread(self, session, of)

    def new_form_xfer(self, session, direction):
        msg = _("Message transfer of %s started with %s") % (session.name,
                                                             session._st)
        self.emit("session-status-update", session._id, msg)

        if direction == "in":
            dd = self.config.form_store_dir()
            self.sthreads[session._id] = FormRecvThread(self, session, dd)
        elif direction == "out":
            of = self.outgoing_forms.pop()
            self.sthreads[session._id] = FormSendThread(self, session, of)

    def new_socket(self, session, direction):
        msg = _("Socket session %s started with %s") % (session.name,
                                                        session._st)
        self.emit("session-status-update", session._id, msg)

        to = float(self.config.get("settings", "sockflush"))

        try:
            foo, port = session.name.split(":", 2)
            port = int(port)
        except Exception as e:
            printlog("SessCoord"," : Invalid socket session name %s: %s" % (session.name, e))
            session.close()
            return

        if direction == "in":
            try:
                ports = self.config.options("tcp_in")
                for _portspec in ports:
                    portspec = self.config.get("tcp_in", _portspec)
                    p, h = portspec.split(",")
                    p = int(p)
                    if p == port:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.connect((h, port))
                        self.sthreads[session._id] = SocketThread(self,
                                                                  session,
                                                                  (sock, to))
                        return

                raise Exception("Port %i not configured" % port)
            except Exception as e:
                msg = _("Error starting socket session: %s") % e
                self.emit("session-status-update", session._id, msg)
                session.close()

        elif direction == "out":
            sock = self.socket_listeners[port].dsock
            self.sthreads[session._id] = SocketThread(self, session, (sock, to))

    @run_gtk_locked
    def _new_session(self, type, session, direction):
        if session._id <= 3:
            return # Skip control, chat, sniff, rpc

        printlog("SessCoord"," : New session (%s) of type: %s" % (direction, session.__class__))
        self.emit("session-started", session._id, type)

        if isinstance(session, form.FormTransferSession):
            self.new_form_xfer(session, direction)
        elif isinstance(session, file.FileTransferSession):
            self.new_file_xfer(session, direction)
        elif isinstance(session, sock.SocketSession):
            self.new_socket(session, direction)
        else:
            printlog("SessCoord"," : *** Unknown session type: %s" % session.__class__.__name__)

    def new_session(self, type, session, direction):
        gobject.idle_add(self._new_session, type, session, direction)

    def end_session(self, id):
        thread = self.sthreads.get(id, None)
        if isinstance(thread, SessionThread):
            del self.sthreads[id]
        else:
            self._emit("session-ended", id, "Ended", None) 

    def session_cb(self, data, reason, session):
        t = str(session.__class__.__name__).replace("Session", "")
        if "." in t:
            t = t.split(".")[2]

        if reason.startswith("new,"):
            self.new_session(t, session, reason.split(",", 2)[1])
        elif reason == "end":
            self.end_session(session._id)

    def send_file(self, dest, filename, name=None):
        if name is None:
            name = os.path.basename(filename)

        self.outgoing_files.insert(0, filename)
        printlog("SessCoord"," : Outgoing files: %s" % self.outgoing_files)

        xfer = file.FileTransferSession
        bs = self.config.getint("settings", "ddt_block_size")
        ol = self.config.getint("settings", "ddt_block_outlimit")

        t = threading.Thread(target=self.sm.start_session,
                             kwargs={"name"      : name,
                                     "dest"      : dest,
                                     "cls"       : xfer,
                                     "blocksize" : bs,
                                     "outlimit"  : ol})
        t.setDaemon(True)
        t.start()
        printlog("SessCoord"," : Started Session")
        
    def send_form(self, dest, filename, name="Form"):
        self.outgoing_forms.insert(0, filename)
        printlog("SessCoord"," : Outgoing forms: %s" % self.outgoing_forms)

        xfer = form.FormTransferSession

        t = threading.Thread(target=self.sm.start_session,
                             kwargs={"name" : name,
                                     "dest" : dest,
                                     "cls"  : xfer})
        t.setDaemon(True)
        t.start()
        printlog("SessCoord"," : Started form session")

    def __init__(self, config, sm):
        gobject.GObject.__init__(self)

        self.sm = sm
        self.config = config

        self.sthreads = {}

        self.outgoing_files = []
        self.outgoing_forms = []

        self.socket_listeners = {}

    def shutdown(self):
        for dport, listener in self.socket_listeners.items():
            printlog("SessCoord"," : Stopping TCP:%i" % dport)
            listener.stop()
