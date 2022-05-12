#
'''Session Coordinator'''
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

from __future__ import absolute_import
from __future__ import print_function

import logging
import socket
import threading
import time
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib
from gi.repository import GObject

from d_rats.sessions import base
from d_rats.sessions import file as sessions_file
from d_rats.sessions import form
from d_rats.sessions import sock
from .utils import run_safe, run_gtk_locked
from . import formgui

# from . import emailgw
from . import signals
from . import msgrouting

if not '_' in locals():
    import gettext
    _ = gettext.gettext


class SessionCoordinatorException(Exception):
    '''Generic Session Coordinator Exception.'''


class ListenerActiveError(SessionCoordinatorException):
    '''Listener is already Active Error.'''


class PortNotConfigError(SessionCoordinatorException):
    '''Port is not Configured Error.'''


class SocketIsClosedError(SessionCoordinatorException):
    '''Socket is Closed Error.'''


class SessionThread():
    '''
    Session Thread.

    :param coord: Coordinates?
    :param session: Session object
    :param data: Session thread data
    '''
    OUTGOING = False

    def __init__(self, coord, session, data):

        self.logger = logging.getLogger("SessionThread")
        self.enabled = True
        self.coord = coord
        self.session = session
        self.arg = data

        self.thread = threading.Thread(target=self.worker, args=(data,))
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        '''Stop.'''
        self.enabled = False
        self.thread.join()

    def worker(self, _path):
        '''
        Worker.

        :param _path: Unused, arguments for base case
        :type _path: str
        '''
        self.logger.info("worker: **** EMPTY SESSION THREAD ****")


class FileBaseThread(SessionThread):
    '''
    File Base Thread.

    :param args: Arguments for SessionThread
    '''

    progress_key = "recv_size"

    def __init__(self, *args):
        SessionThread.__init__(self, *args)

        self.pct_complete = 0.0

        self.session.status_cb = self.status_cb

    @run_safe
    def status_cb(self, vals):
        '''
        Status call back.

        :param vals: data for callback
        '''
        # print "GUI Status:"
        # for k,v in vals.copy().items():
        #     print "   -> %s: %s" % (k, v)

        if vals["total_size"]:
            pct = (float(vals[self.progress_key]) / vals["total_size"]) * 100.0
        else:
            pct = 0.0

        if vals["retries"] > 0:
            retries = " (%i retries)" % vals["retries"]
        else:
            retries = ""

        speed = ""
        if "start_time" in vals:
            elapsed = time.time() - vals["start_time"]
            if elapsed:
                kbytes = vals[self.progress_key]
                speed = " %2.2f B/s" % (kbytes / elapsed)

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
        '''
        Completed.

        :param objname: Name of object, default None.
        '''
        self.coord.session_status(self.session, _("Transfer Completed"))

        if objname:
            _msg = " of %s" % objname
        else:
            _msg = ""

        size = self.session.stats["total_size"]
        if size > 1024:
            size >>= 10
            units = "KB"
        else:
            units = "B"

        if "start_time" in self.session.stats:
            start = self.session.stats["start_time"]
            _exmsg = " (%i%s @ %2.2f B/s)" % (\
                size, units,
                self.session.stats["total_size"] /
                (time.time() - start))
        else:
            _exmsg = ""

    def failed(self, restart_info=None):
        '''
        Failed.

        :param restart_info: Restart information, default None
        '''
        status = _("Transfer Interrupted") + \
            " (%.0f%% complete)" % self.pct_complete

        self.coord.session_failed(self.session, status, restart_info)


class FileRecvThread(FileBaseThread):
    '''File Receive Thread.'''

    def worker(self, path):
        '''
        Worker.

        :param path: Path for file to be received
        :type path: str
        '''
        file_name = self.session.recv_file(path)
        if file_name:
            self.completed("file %s" % os.path.basename(file_name))
            self.coord.session_newfile(self.session, file_name)
        else:
            self.failed()


class FileSendThread(FileBaseThread):
    '''File Send Thread.'''

    OUTGOING = True
    progress_key = "sent_size"

    def worker(self, path):
        '''
        Worker.

        :param path: Path for file to be sent
        :type path: str
        '''
        if self.session.send_file(path):
            self.completed("file %s" % os.path.basename(path))
            self.coord.session_file_sent(self.session, path)
        else:
            self.failed((self.session.get_station(), path))


class FormRecvThread(FileBaseThread):
    '''Form Receive Thread.'''

    def __init__(self, *args):
        FileBaseThread.__init__(self, *args)
        self.logger = logging.getLogger("FormRecvThread")

    def worker(self, _path):
        '''
        Worker.

        :param _path: Unused arguments
        '''
        m_dir = os.path.join(self.coord.config.form_store_dir(), _("Inbox"))
        newfn = time.strftime(os.path.join(m_dir, "form_%m%d%Y_%H%M%S.xml"))
        if not msgrouting.msg_lock(newfn):
            self.logger.info("worker: "
                             "AIEE! Unable to lock incoming new message file!")

        file_name = self.session.recv_file(newfn)

        _name = "%s %s %s" % (self.session.name,
                              _("from"),
                              self.session.get_station())

        if file_name == newfn:
            worker_form = formgui.FormFile(file_name)
            worker_form.add_path_element(self.coord.config.get("user",
                                                               "callsign"))
            worker_form.save_to(file_name)

            self.completed("form")
            self.coord.session_newform(self.session, file_name)
        else:
            self.failed()
            self.logger.info("worker: <--- Form transfer failed -->")


class FormSendThread(FileBaseThread):
    '''Form Send Thread.'''

    OUTGOING = True
    progress_key = "sent_size"

    def worker(self, path):
        '''
        Worker.

        :param path: Path to send form?
        :type path: str
        '''
        if self.session.send_file(path):
            self.completed()
            self.coord.session_form_sent(self.session, path)
        else:
            self.failed((self.session.get_station(), path))


class SocketThread(SessionThread):
    '''
    Socket Thread.

    :param coord: Coordinates?
    :param session: Session object
    :param data: Session thread data
    '''
    OUTGOING = False

    def __init__(self, coord, session, data):
        SessionThread.__init__(self, coord, session, data)
        self.logger = logging.getLogger("SessionThread")

    def status(self):
        '''Status.'''
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

    @staticmethod
    def socket_read(read_sock, length, time_out=5):
        '''
        Socket read.

        :param read_sock: Socket to read from
        :param length: Amount of data to read
        :type length: int
        :param time_out: Time out for read, default 5 seconds
        :type time_out: float
        :raises: :class:`SocketIsClosedError` if the socket is closed.
        '''
        data = ""
        start_time = time.time()

        while (time.time() - start_time) < time_out:
            read_data = ""

            try:
                read_data = read_sock.recv(length - len(read_data))
            except socket.timeout:
                continue

            if not read_data and not data:
                raise SocketIsClosedError("Socket is closed")

            data += read_data

        return data

    def worker(self, data):
        '''
        Worker.

        :param data: Tuple of a socket and a timeout
        :type data: tuple
        '''
        (worker_sock, timeout) = data

        self.logger.info("worker: *** Socket thread alive (%i timeout)",
                         timeout)

        worker_sock.settimeout(timeout)

        while self.enabled:
            start_time = time.time()
            try:
                send_data = self.socket_read(worker_sock, 512, timeout)
            except SocketIsClosedError as err:
                self.logger.info("worker socket read %s", err)
                break
            self.logger.info("worker: Waited %f sec for socket",
                             (time.time() - start_time))

            try:
                read_data = self.session.read(512)
            except base.SessionClosedError:
                self.logger.info("Session closed")
                self.enabled = False
                break

            self.status()

            if send_data:
                self.logger.info("worker: Sending socket data (%i)",
                                 len(send_data))
                self.session.write(send_data)

            if read_data:
                self.logger("worker : Sending radio data (%i)",
                            len(read_data))
                worker_sock.sendall(read_data)

        self.logger.info("Closing session")

        self.session.close()
        try:
            worker_sock.close()
        # On Windows, ConnectionError not based on OSError
        except (ConnectionError, OSError):
            pass

        self.logger.info("*** Socket thread exiting")


class SessionCoordinator(GObject.GObject):
    '''
    Session Coordinator.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param session_manager: Session object
    '''

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

    def __init__(self, config, session_manager):
        GObject.GObject.__init__(self)

        self.logger = logging.getLogger("SessionCoordinator")
        self.session_manager = session_manager
        self.config = config

        self.sthreads = {}

        self.outgoing_files = []
        self.outgoing_forms = []

        self.socket_listeners = {}

    def _emit(self, signal, *args):
        GLib.idle_add(self.emit, signal, *args)

    def session_status(self, session, msg):
        '''
        Session status.

        :param session: Session object
        :param msg: Status message
        :type msg: str
        '''
        # pylint: disable=protected-access
        self._emit("session-status-update", session._id, msg)

    def session_newform(self, session, path):
        '''
        Session new form.

        :param session: Session object
        :param path: Path of file or session?
        :type path: str
        '''
        # pylint: disable=protected-access
        self._emit("form-received", session._id, path)

    def session_newfile(self, session, path):
        '''
        Session new file.

        :param session: Session object
        :param path: Path of file or session?
        :type path: str
        '''
        # pylint: disable=protected-access
        self._emit("file-received", session._id, path)

    def session_form_sent(self, session, path):
        '''
        Session form sent.

        :param session: Session object
        :param path: Path of form or session?
        :type path: str
        '''
        # pylint: disable=protected-access
        self._emit("form-sent", session._id, path)

    def session_file_sent(self, session, path):
        '''
        Session file sent.

        :param session: Session object
        :param path: Path of file or session?
        :type path: str
        '''
        # pylint: disable=protected-access
        self._emit("file-sent", session._id, path)

    def session_failed(self, session, msg, restart_info=None):
        '''
        Session failed.

        :param session: Session object
        :param msg: Status message
        :type msg: str
        :param restart_info: Restart information, default None
        '''
        # pylint: disable=protected-access
        self._emit("session-ended", session._id, msg, restart_info)

    def cancel_session(self, ident, force=False):
        '''
        Cancel Session

        :param ident: Session identification
        :type ident: int
        :param force: Force the session closed, default False
        :type force: bool
        '''
        if ident < 2:
            # Don't let them cancel Control or Chat
            return

        try:
            session = self.session_manager.sessions[ident]
        except KeyError as err:
            self.logger.info("cancel_session:"
                             "Session `%i' not found: %s",
                             ident, err)
            return

        if ident in self.sthreads:
            del self.sthreads[ident]
        session.close(force)

    def create_socket_listener(self, sport, dport, dest):
        '''
        Create socket listener.

        :param sport: Source port
        :type sport: int
        :param dport: Destination port
        :type dport: int
        :param dest: Destination host
        :type dest: str
        :raises: :class:`ListenerActiveError` if the listener is already in use
        '''
        if dport not in list(self.socket_listeners):
            self.logger.info("Starting a listener for port %i->%s:%i",
                             sport, dest, dport)
            self.socket_listeners[dport] = \
                sock.SocketListener(self.session_manager, dest, sport, dport)
            self.logger.info("Started")
        else:
            raise ListenerActiveError("Listener for %i already active" % dport)

    def new_file_xfer(self, session, direction):
        '''
        New file transfer.

        :param session: Session object
        :param direction: Direction of transfer
        :type direction: str
        '''
        # pylint: disable=protected-access
        msg = _("File transfer of %s started with %s") % \
                (session.name, session._st)
        # pylint: disable=protected-access
        self.emit("session-status-update", session._id, msg)

        if direction == "in":
            download_dir = self.config.get("prefs", "download_dir")
            # pylint: disable=protected-access
            self.sthreads[session._id] = FileRecvThread(self, session,
                                                        download_dir)
        elif direction == "out":
            output_form = self.outgoing_files.pop()
            # pylint: disable=protected-access
            self.sthreads[session._id] = FileSendThread(self, session,
                                                        output_form)

    def new_form_xfer(self, session, direction):
        '''
        New form transfer.

        :param session: Session object
        :param direction: Direction of transfer
        :type direction: str
        '''
        # pylint: disable=protected-access
        msg = _("Message transfer of %s started with %s") % (session.name,
                                                             session._st)
        # pylint: disable=protected-access
        self.emit("session-status-update", session._id, msg)

        if direction == "in":
            form_store_dir = self.config.form_store_dir()
            # pylint: disable=protected-access
            self.sthreads[session._id] = FormRecvThread(self, session,
                                                        form_store_dir)
        elif direction == "out":
            output_form = self.outgoing_forms.pop()
            # pylint: disable=protected-access
            self.sthreads[session._id] = FormSendThread(self, session,
                                                        output_form)

    def new_socket(self, session, direction):
        '''
        New socket.

        :param session: Session object
        :param direction: Direction of transfer
        :type direction: str
        :raises: :class:`PortNotConfigError` if the port is not configured
        '''
        # pylint: disable=protected-access
        msg = _("Socket session %s started with %s") % (session.name,
                                                        session._st)
        # pylint: disable=protected-access
        self.emit("session-status-update", session._id, msg)

        time_out = float(self.config.get("settings", "sockflush"))

        try:
            _foo, session_port = session.name.split(":", 2)
            session_port = int(session_port)
        except ValueError as err:
            self.logger.info("new_socket: Invalid socket session name %s: %s",
                             session.name, err)
            session.close()
            return

        if direction == "in":
            try:
                ports = self.config.options("tcp_in")
                for _portspec in ports:
                    portspec = self.config.get("tcp_in", _portspec)
                    port, host = portspec.split(",")
                    port = int(session_port)
                    if port == session_port:
                        new_sock = socket.socket(socket.AF_INET,
                                                 socket.SOCK_STREAM)
                        new_sock.connect((host, port))
                        # pylint: disable=protected-access
                        self.sthreads[session._id] = SocketThread(self,
                                                                  session,
                                                                  (new_sock,
                                                                   time_out))
                        return

                raise PortNotConfigError("Port %i not configured" %
                                         session_port)

            # On Windows, ConnectionError not based on OSError
            except (ConnectionError, OSError, PortNotConfigError) as err:
                msg = _("Error starting socket session: ") + str(err)
                self.emit("session-status-update", session._id, msg)
                session.close()

        elif direction == "out":
            new_sock = self.socket_listeners[session_port].dsock
            # pylint: disable=protected-access
            self.sthreads[session._id] = SocketThread(self, session,
                                                      (new_sock, time_out))

    @run_gtk_locked
    def _new_session(self, session_type, session, direction):
        # pylint: disable=protected-access
        if session._id <= 3:
            return # Skip control, chat, sniff, rpc

        self.logger.info("New session (%s) of type: %s",
                         direction, session.__class__)
        # pylint: disable=protected-access
        self.emit("session-started", session._id, session_type)

        if isinstance(session, form.FormTransferSession):
            self.new_form_xfer(session, direction)
        elif isinstance(session, sessions_file.FileTransferSession):
            self.new_file_xfer(session, direction)
        elif isinstance(session, sock.SocketSession):
            self.new_socket(session, direction)
        else:
            self.logger.info("_new_session: *** Unknown session type: %s",
                             session.__class__.__name__)

    def new_session(self, session_type, session, direction):
        '''
        New session.

        :param session_type: Type of session
        :param session: Session name
        :type session: str
        :param direction: Direction of session
        :type direction: str
        '''
        GLib.idle_add(self._new_session, session_type, session, direction)

    def end_session(self, ident):
        '''
        End Session.

        :param ident: Session identification
        '''
        thread = self.sthreads.get(ident, None)
        if isinstance(thread, SessionThread):
            del self.sthreads[ident]
        else:
            self._emit("session-ended", ident, "Ended", None)

    def session_cb(self, data, reason, session):
        '''
        Session call back.

        :param data: Data for callback
        :param reason: Reason for call back
        :param session: Session object
        '''
        session_type = str(session.__class__.__name__).replace("Session", "")
        if "." in session_type:
            session_type = session_type.split(".")[2]

        if reason.startswith("new,"):
            self.new_session(session_type, session, reason.split(",", 2)[1])
        elif reason == "end":
            # pylint: disable=protected-access
            self.end_session(session._id)

    def send_file(self, dest, filename, name=None):
        '''
        Send file.

        :param dest: Destination call sign
        :type dest: str
        :param filename: Filename to send
        :type filename: str
        :param name: Session Name, default filename with out path
        :type name: str
        '''
        if name is None:
            name = os.path.basename(filename)

        self.outgoing_files.insert(0, filename)
        self.logger.info("send_file: Outgoing files: %s", self.outgoing_files)

        xfer = sessions_file.FileTransferSession
        block_size = self.config.getint("settings", "ddt_block_size")
        outlimit = self.config.getint("settings", "ddt_block_outlimit")

        file_thread = threading.Thread(
            target=self.session_manager.start_session,
            kwargs={"name"      : name,
                    "dest"      : dest,
                    "cls"       : xfer,
                    "blocksize" : block_size,
                    "outlimit"  : outlimit})
        file_thread.daemon = True
        file_thread.start()
        self.logger.info("send_file: Started Session")

    def send_form(self, dest, filename, name="Form"):
        '''
        Send Form.

        :param dest: Destination call sign
        :type dest: str
        :param filename: Filename of form
        :type filename: str
        :param name: Session name, default "Form"
        :type name: str
        '''
        self.outgoing_forms.insert(0, filename)
        self.logger.info("send_form: Outgoing forms: %s", self.outgoing_forms)

        xfer = form.FormTransferSession

        form_thread = threading.Thread(
            target=self.session_manager.start_session,
            kwargs={"name" : name,
                    "dest" : dest,
                    "cls"  : xfer})
        form_thread.daemon = True
        form_thread.start()
        self.logger.info("Started form session")

    def shutdown(self):
        '''Shutdown.'''
        for dport, listener in self.socket_listeners.copy().items():
            self.logger.info("shutdown: Stopping TCP:%i", dport)
            listener.stop()
