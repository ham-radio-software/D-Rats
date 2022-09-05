#!/usr/bin/python
'''RPC'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Python3 update Copyright 2021 John Malmberg <wb8tyw@qsl.net>
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
import time
import datetime
import logging
import os
import glob
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject
from gi.repository import GLib

from d_rats import ddt2, signals, emailgw, wl2k

# This feels wrong
from d_rats.ui import main_events

from d_rats.sessions import base, stateless
from d_rats.version import DRATS_VERSION
from d_rats.utils import log_exception


if not '_' in locals():
    import gettext
    _ = gettext.gettext

ASCII_FS = "\x1C"
ASCII_GS = "\x1D"
ASCII_RS = "\x1E"
ASCII_US = "\x1F"


class RPCException(Exception):
    '''Generic RPC Exception'''


class UnknownRPCCall(RPCException):
    '''Unknown RPC Call.'''


class InvalidRPCDictKey(RPCException):
    '''Invalid type for Dictionary Key encoding.'''


class InvalidRPCDictValue(RPCException):
    '''Invalid type for Dictionary value encoding.'''


class MalformedRPCDictEncoding(RPCException):
    '''Invalid type for Dictionary value encoding.'''


class RPCResultNotDict(RPCException):
    '''Results must be a Dictionary type.'''


class RPCInvalidStatus(RPCException):
    '''Status is not a known RPC status value.'''


class RPCActionSetRequired(RPCException):
    '''RPCSession needs an rpcactions parameter.'''


if sys.version_info[0] > 2:
    # pylint: disable=invalid-name
    class basestring(str):
        '''Suppress pylint on python3 warning.'''


def encode_dict(source):
    '''
    Encode Dictionary into a string.

    :param source: Source Dictionary
    :type source: dict
    :returns: encoded data
    :rtype: string
    '''
    elements = []

    for key, value in source.items():
        if not isinstance(key, str):
            raise InvalidRPCDictKey("Cannot encode non-string dict key")

        if isinstance(value, bytearray):
            value = value.decode('utf-8', 'replace')
        # python 3 type must be 'str'
        # python 2 type must be of 'basestring'
        elif sys.version_info[0] > 2:
            if not isinstance(value, str):
                raise InvalidRPCDictValue(
                    "Cannot encode non-string dict value")
        # Have to live with this pylint warning on python3 for now.
        # and also add a pylance ignore for it.
        elif not isinstance(value, basestring):  # type: ignore
            raise InvalidRPCDictValue("Cannot encode non-string dict value")

        elements.append(key + ASCII_US + value)
    return ASCII_RS.join(elements)


def decode_dict(string):
    '''
    Decode into Dictionary.

    :param string: Encoded string
    :returns: Decoded data
    :rtype: dict
    '''
    result = {}
    if not string:
        return result
    elements = string.split(ASCII_RS)
    for element in elements:
        try:
            key, value = element.split(ASCII_US)
        except ValueError:
            raise MalformedRPCDictEncoding("Malformed dict encoding")
        # sockets and pipe routines return bytearray type
        # which on python2 is almost the same str type, but not quite.
        if isinstance(key, bytearray):
            key = key.decode('ISO-8859-1')
        # Just about everything will want a utf-8 string for the value.
        if isinstance(value, bytearray):
            result[key] = value.decode('utf-8', 'replace')
        else:
            result[key] = value

    return result


class RPCJob(GObject.GObject):
    '''
    RPC Job Parent Class.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''
    __gsignals__ = {
        "state-change" : (GObject.SIGNAL_RUN_LAST,
                          GObject.TYPE_NONE,
                          (GObject.TYPE_STRING, GObject.TYPE_PYOBJECT)),
        }

    STATES = ["complete", "timeout", "running"]

    def __init__(self, dest, desc):
        GObject.GObject.__init__(self)
        self.__dest = dest
        self.__desc = desc
        self._args = {}

    def get_dest(self):
        '''
        Get destination.

        :returns: Destination
        '''
        return self.__dest

    def get_desc(self):
        '''
        Get Description.

        :returns: Description
        '''
        return self.__desc

    def set_state(self, state, result=None):
        '''
        Set state

        :param state: State to set
        :param result: Optional dict of results
        '''
        if result is None:
            result = {}
        if not isinstance(result, dict):
            raise RPCResultNotDict("Value of result property must be dict")
        if state in self.STATES:
            GObject.idle_add(self.emit, "state-change", state, result)
        else:
            raise RPCInvalidStatus("Invalid status `%s'" % state)

    def unpack(self, raw):
        '''
        Unpack the data

        :returns: Unpacked data.
        '''
        self._args = {}
        if not raw:
            self._args = {}
        else:
            self._args = decode_dict(raw)

    def pack(self):
        '''
        Pack the data

        :returns: Encoded dict
        '''
        return encode_dict(self._args)

    # pylint: disable=no-self-use, invalid-name
    def do(self, _rpcactions):
        '''
        Do RPC job.

        :param _rpcactions: RPC Action object
        :returns: Result of RPC call
        '''
        return {"rc" : "Unsupported Job Type"}


class RPCFileListJob(RPCJob):
    '''
    RPC File List Job.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''

    def set_file_list(self, file_list):
        '''
        Set file list.

        :param file_list: List of files
        '''
        self._args = {}
        for item in file_list:
            self._args[item] = ""

    def get_file_list(self):
        '''
        Get file list.

        :returns: List of files
        '''
        return list(self._args.keys())

    def do(self, rpcactions):
        '''
        Do File List.

        :param rpcactions: RPC Action object
        :returns: Result of RPC call
        '''
        return rpcactions.RPC_file_list(self)


class RPCFormListJob(RPCJob):
    '''
    RPC Form List Job.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''

    # pylint: disable=no-self-use
    def get_form_list(self):
        '''
        Get Form List.

        :returns: Form list
        '''
        return []

    def do(self, rpcactions):
        '''
        Do Get Form List.

        :param rpcactions: RPC Action object
        :returns: Result of RPC call
        '''
        return rpcactions.RPC_form_list(self)


class RPCPullFileJob(RPCJob):
    '''RPC Pull File Job.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''

    def set_file(self, filename):
        '''
        Set File to pull.

        :param filename: Filename to pull
        '''
        self._args = {"fn" : filename}

    def get_file(self):
        '''
        Get pulled filename.

        :returns: Filename of file pulled
        '''
        return self._args.get("fn", None)

    def do(self, rpcactions):
        '''
        Do Pull File.

        :param rpcactions: RPC Action object
        :returns: Result of RPC call
        '''
        return rpcactions.RPC_file_pull(self)


class RPCDeleteFileJob(RPCJob):
    '''
    RPC Delete File Job.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''

    def set_file(self, filename):
        '''
        Set file for deletion.

        :param filename: Name of file
        '''
        self._args["fn"] = filename

    def set_pass(self, passwd):
        '''
        Set Password for file deletion

        :param passwd: Password
        '''
        self._args["passwd"] = passwd

    def get_file(self):
        '''
        Get Filename to be deleted.

        :returns: Filename
        '''
        return self._args.get("fn", None)

    def get_pass(self):
        '''
        Get Password

        :returns: Password for deleting file
        '''
        return self._args.get("passwd", "")

    def do(self, rpcactions):
        '''
        Do Delete File.

        :param rpcactions: RPC Action object
        :returns: Result of RPC call
        '''
        return rpcactions.RPC_file_delete(self)


class RPCPullFormJob(RPCJob):
    '''
    RPC Pull Form Job.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''

    def set_form(self, form):
        '''
        Set Form.

        :param form: Form to send
        '''
        self._args = {"fn" : form}

    def get_form(self):
        '''
        Get Form.

        :returns: Form from job
        '''
        return self._args.get("fn", None)

    def do(self, rpcactions):
        '''
        Do Pull Form.

        :param rpcactions: RPC Action object
        :returns: Result of RPC call
        '''
        return rpcactions.RPC_form_pull(self)


class RPCPositionReport(RPCJob):
    '''
    RPC Position Report.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''

    def set_station(self, station):
        '''
        Set Station

        :param station: Station for position report
        '''
        self._args = {"st" : station}

    def get_station(self):
        '''
        Get Station.

        :returns: Station from position report
        '''
        return self._args.get("st", "ERROR")

    def do(self, rpcactions):
        '''
        Do Get Position Report.

        :param rpcactions: RPC Action object
        :returns: Result of RPC call
        '''

        return rpcactions.RPC_pos_report(self)


class RPCGetVersion(RPCJob):
    '''
    RPC Get Version.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''

    def do(self, rpcactions):
        '''
        Do Get version.

        :param rpcactions: RPC Action object
        :returns: Result of RPC call
        '''
        return rpcactions.RPC_get_version(self)


class RPCCheckMail(RPCJob):
    '''
    RPC Check Mail.

    :param dest: Destintion of job
    :type dest: str
    :param desc: Description of job
    :type desc: str
    '''

    def do(self, rpcactions):
        '''
        Do Check Mail.

        :param rpcactions: RPC Action object
        :returns: Result of RPC call
        '''
        return rpcactions.RPC_check_mail(self)

    # pylint: disable=too-many-arguments
    def set_account(self, host, user, pasw, port, ssl):
        '''
        Set Mail Account.

        :param host: TCP/IP Host name
        :param user: User name
        :param pasw: Password for user
        :param port: TCP/IP port
        :param port: SSL flag
        '''
        self._args = {"host" : host,
                      "user" : user,
                      "pasw" : pasw,
                      "port" : port,
                      "ssl"  : ssl,
                      }

    def get_account(self):
        '''
        Get Mail account.

        :returns: Tuple with account information
        '''
        return self._args["host"], self._args["user"], self._args["pasw"], \
            int(self._args["port"]), self._args["ssl"] == "True"


class RPCSession(GObject.GObject, stateless.StatelessSession):
    '''
    RPC Session.

    :param args: Variable arguments
    :param rpcactions: Action set for RPC session
    :param kwargs: Keyword arguments
    '''
    type = base.T_RPC

    T_RPCREQ = 0
    T_RPCACK = 1

    def __init__(self, *args, **kwargs):
        GObject.GObject.__init__(self)

        self.logger = logging.getLogger("RPCSession")
        try:
            self.__rpcactions = kwargs["rpcactions"]
            del kwargs["rpcactions"]
        except KeyError:
            raise RPCActionSetRequired("RPCSession requires RPCActionSet")

        stateless.StatelessSession.__init__(self, *args, **kwargs)
        self.__jobs = {}
        self.__jobq = []
        self.__jobc = 0
        self.__t_retry = 30
        self.__enabled = True

        GLib.timeout_add(1000, self.__worker)

        self.handler = self.incoming_data

    # pylint: disable=arguments-differ
    def notify(self):
        pass

    # pylint: disable=no-self-use
    def __decode_rpccall(self, frame):
        jobtype, args = frame.data.split(ASCII_GS)
        # pylint: disable=fixme
        # FIXME: Make this more secure
        if not (jobtype.isalpha() and jobtype.startswith("RPC")):
            raise UnknownRPCCall("Unknown call `%s'" % jobtype)

        # pylint: disable=eval-used
        job = eval("%s('%s', 'New job')" % (jobtype, frame.s_station))
        job.unpack(args)

        return job

    # pylint: disable=no-self-use
    def __encode_rpccall(self, job):
        return "%s%s%s" % (job.__class__.__name__, ASCII_GS, job.pack())

    def __get_seq(self):
        self.__jobc += 1
        return self.__jobc

    def __job_to_frame(self, job, ident):
        frame = ddt2.DDT2EncodedFrame()
        frame.type = self.T_RPCREQ
        frame.seq = ident
        frame.data = self.__encode_rpccall(job)
        frame.d_station = job.get_dest()

        return frame

    def __send_job_status(self, ident, station, _state, result):
        frame = ddt2.DDT2EncodedFrame()
        frame.type = self.T_RPCACK
        frame.seq = ident
        frame.data = result
        frame.d_station = station

        return frame

    def __job_state(self, job, state, _result, ident):
        self.logger.info("__job_state: Job state: %s for %i: %s",
                         state, ident, _result)

        if state == "running":
            return

        result = encode_dict(_result)
        frame = self.__send_job_status(ident, job.get_dest(), state, result)
        self._sm.outgoing(self, frame)

    def incoming_data(self, frame):
        '''
        Incoming Data.

        :param frame: Frame of data
        '''
        if frame.type == self.T_RPCREQ:
            try:
                job = self.__decode_rpccall(frame)
            except UnknownRPCCall:
                self.logger.info("incoming data : unable to execute"
                                 " RPC from %s",
                                 frame.s_station, exc_info=True)
                return

            job.connect("state-change", self.__job_state, frame.seq)
            result = job.do(self.__rpcactions)
            if result is not None:
                job.set_state("complete", result)

        elif frame.type == self.T_RPCACK:
            if frame.seq in self.__jobs:
                _ts, _att, job = self.__jobs[frame.seq]
                del self.__jobs[frame.seq]
                job.set_state("complete", decode_dict(frame.data))
            else:
                self.logger.info("incoming data : Unknown job %i", frame.seq)

        else:
            self.logger.info("incoming data : Unknown RPC frame type %i",
                             frame.type)

    def __send_job(self, job, ident):
        self.logger.info("Sending job `%s' to %s",
                         job.get_desc(), job.get_dest())
        frame = self.__job_to_frame(job, ident)
        job.frame = frame
        self._sm.outgoing(self, frame)
        self.logger.info("Job sent")

    def __worker(self):
        for ident, (time_stamp, att, job) in self.__jobs.items():
            if job.frame and not job.frame.sent_event.isSet():
                # Reset timer until the block is sent
                self.__jobs[ident] = (time.time(), att, job)
            elif (time.time() - time_stamp) > self.__t_retry:
                self.logger.info("worker: Cancelling job %i due to timeout",
                                 ident)
                del self.__jobs[ident]
                job.set_state("timeout")

        return True

    def submit(self, job):
        '''
        Submit Session.

        :param job: Job for session
        '''
        ident = self.__get_seq()
        self.__send_job(job, ident)
        self.__jobs[ident] = (time.time(), 0, job)

    def stop(self):
        '''Stop Session.'''
        self.__enabled = False


class RPCActionSet(GObject.GObject):
    '''
    RPC Action Set.

    :param config: Config object
    :param port: Radio port
    '''
    __gsignals__ = {
        "rpc-send-file" : signals.RPC_SEND_FILE,
        "rpc-send-form" : signals.RPC_SEND_FORM,
        "get-message-list" : signals.GET_MESSAGE_LIST,
        "get-current-position" : signals.GET_CURRENT_POSITION,
        "user-send-chat" : signals.USER_SEND_CHAT,
        "event" : signals.EVENT,
        "register-object" : signals.REGISTER_OBJECT,
        "form-received" : signals.FORM_RECEIVED,
        "form-sent" : signals.FORM_SENT,
        }

    _signals = __gsignals__

    def __init__(self, config, port):
        self.logger = logging.getLogger("RPCActionSet")
        self.__config = config
        self.__port = port

        GObject.GObject.__init__(self)

    def __proxy_emit(self, signal):
        def handler(_obj, *args):
            self.logger.info("Proxy emit %s: %s", signal, args)
            GObject.idle_add(self.emit, signal, *args)

        return handler

    # pylint: disable=invalid-name
    def RPC_pos_report(self, job):
        '''
        RPC Position Report.

        :param job: Job request is for
        :type job: :class:`RPCPositionReport`
        :returns: Result
        :rtype: dict
        '''
        result = {}
        mycall = self.__config.get("user", "callsign")
        rqcall = job.get_station()

        self.logger.info("Position request for `%s'", rqcall)
        self.logger.info("Position Report: Self=%s", format(self))

        if rqcall in (mycall, "."):
            rqcall = None
        try:
            #obtaining current position from config or local gps
            fix = self.emit("get-current-position", rqcall)
            #result = fix.to_NMEA_GGA()
            result["rc"] = "True"
            symtab = self.__config.get("settings", "aprssymtab")
            symbol = self.__config.get("settings", "aprssymbol")
            result["msg"] = fix.to_APRS(symtab=symtab, symbol=symbol)

        # pylint: disable=broad-except
        except Exception:
            self.logger.info("RPC_pos_report: Case KO :"
                             "broad-exception while getting"
                             " position of %s",
                             rqcall, exc_type=True)
            log_exception()
            fix = None
            result["rc"] = "False"
            result["msg"] = " No data for station '%s'" % job.get_station()

        if fix:
            # sending the position to transport // but this is broken!!
            self.logger.info("RPC_pos_report: port is : %s", self.__port)
            self.logger.info("RPC_pos_report: fix is: %s", fix)
            self.logger.info("RPC_pos_report: fix in NMEA GGA is: %s",
                             fix.to_NMEA_GGA())
            self.logger.info("RPC_pos_report: fix in APRS is: %s", result)

            self.emit("user-send-chat",
                      "CQCQCQ",
                      self.__port,
                      result["msg"],
                      True)

    # pylint: disable=invalid-name
    def RPC_file_list(self, job):
        '''
        RPC File List.

        :param job: Job request is for
        :param type: :class:`RPCFileListJob`
        :returns: result
        :rtype: dict
        '''
        result = {}

        download_dir = self.__config.get("prefs", "download_dir")
        files = glob.glob(os.path.join(download_dir, "*.*"))
        for fname in files:
            if os.path.isdir(fname):
                continue
            size = os.path.getsize(fname)
            if size < 1024:
                units = "B"
            else:
                size >>= 10
                units = "KB"

            dates = datetime.datetime.fromtimestamp(os.path.getmtime(fname))

            fname = os.path.basename(fname)
            time_string = dates.strftime("%Y-%m-%d %H:%M:%S")
            result[fname] = "%i %s (%s)" % (size, units, time_string)

        event = main_events.Event(None, job.get_dest() + " " + \
                                      _("Requested file list"))
        self.emit("event", event)

        return result

    # pylint: disable=invalid-name
    def RPC_form_list(self, job):
        '''
        RPC Form List

        :param job: Job request is for
        :type job: :class:`RPCFormListJob`
        :returns: result
        :rtype: dict
        '''
        result = {}
        forms = self.emit("get-message-list", "CQCQCQ")
        for subj, stamp, filen in forms:
            time_stamp = time.localtime(stamp)
            time_string = time.strftime("%b-%d-%Y %H:%M:%S", time_stamp)
            result[filen] = "%s/%s" % (subj, time_string)

        event = main_events.Event(None, job.get_dest() + " " + \
                                      _("Requested message list"))
        self.emit("event", event)

        return result

    # pylint: disable=invalid-name
    def RPC_file_pull(self, job):
        '''
        RPC File Pull.

        :param job: Job request is for
        :type job: :class:`RPCPullFileJob`
        :returns: result
        :rtype: dict
        '''
        result = {}

        if not self.__config.getboolean("prefs", "allow_remote_files"):
            result["rc"] = "Remote file transfers not enabled"
            return result

        download_dir = self.__config.get("prefs", "download_dir")
        path = os.path.join(download_dir, job.get_file())
        self.logger.info("RPC_file_pll: Remote requested %s", path)
        if os.path.exists(path):
            result["rc"] = "OK"
            self.emit("rpc-send-file",
                      job.get_dest(), self.__port, path, job.get_file())
        else:
            result["rc"] = "File not found"

        event = main_events.Event(None, job.get_dest() + " " + \
                                      _("Requested file %s") % job.get_file())
        self.emit("event", event)

        return result

    # pylint: disable=invalid-name
    def RPC_file_delete(self, job):
        '''
        RPC File Delete.

        :param job: Job request is for
        :type job: :class:`RPCDeleteFileJob`
        :returns: Result
        :rtype: dict
        '''
        result = {}

        _permlist = self.__config.get("settings", "delete_from")
        try:
            permlist = _permlist.upper().split(",")
        # pylint: disable=broad-except
        except Exception as err:
            self.logger.info("RPC_file_delete:"
                             " upper().split() broad-exception",
                             exc_info=True)
            result["rc"] = "Access list not properly configured"
            return result

        if job.get_dest().upper() not in permlist:
            result["rc"] = "Access denied for %s" % job.get_dest()
            return result

        passwd = self.__config.get("settings", "remote_admin_passwd")
        if passwd and job.get_pass() != passwd:
            result["rc"] = "Access denied (Incorrect Password)"
            return result

        if "/" in job.get_file():
            result["rc"] = "Access denied (file contains slash)"
            return result

        path = os.path.join(self.__config.get("prefs", "download_dir"),
                            job.get_file())
        if not os.path.exists(path):
            result["rc"] = "File not found (%s)" % job.get_file()
            return result

        try:
            os.remove(path)
            result["rc"] = "File %s deleted" % job.get_file()
        # pylint: disable=broad-except
        except Exception as err:
            self.logger.info("RPC_file_delete"
                             "os.remove %s broad exception",
                             path, exc_info=True)
            result["rc"] = "Unable to delete %s: %s" % (job.get_file(), err)
        return result

    # pylint: disable=invalid-name
    def RPC_form_pull(self, job):
        '''
        RPC form pull.

        :param job: Job request is for
        :rtype: RPCPullFormJob
        :returns: result
        :rtype: dict
        '''
        result = {}

        forms = self.emit("get-message-list", "CQCQCQ")
        result["rc"] = "Form not found"
        subj = 'Form Not found.'
        for subj, _stamp, filen in forms:
            if filen == job.get_form():
                fname = os.path.join(self.__config.platform.config_dir(),
                                     "messages", filen)
                if os.path.exists(fname):
                    result["rc"] = "OK"
                    self.emit("rpc-send-form",
                              job.get_dest(), self.__port, fname, subj)
                break

        event = main_events.Event(None, job.get_dest() + " " + \
                                      _("Requested message %s") % subj)
        self.emit("event", event)

        return result

    # pylint: disable=invalid-name
    def RPC_get_version(self, _job):
        '''
        RPC Get Version.

        :param job: Job request is for
        :type job: :class:`RPCGetVersion`
        :returns: Result of call
        :rtype: dict
        '''
        result = {}

        result["version"] = DRATS_VERSION
        result["os"] = self.__config.platform.os_version_string()
        result["pyver"] = ".".join([str(x) for x in sys.version_info[:3]])
        try:
            from gi.repository import Gtk
            # No more pygtk. but need to keep this field for compatibility
            result["pygtkver"] = 'None'
            result["gtkver"] = "%s.%s.%s" % (
                Gtk.MAJOR_VERSION,
                Gtk.MINOR_VERSION,
                Gtk.MICRO_VERSION)
        except ImportError:
            result["pygtkver"] = result["gtkver"] = "Unknown"
            self.logger.info("RPC_get_version: %s", result)

        return result

    # pylint: disable=invalid-name
    def RPC_check_mail(self, job):
        '''
        RPC Check Mail.

        :param job: Job request is for
        :type job: :class:`RPCCheckMail`
        :returns: result
        :rtype: dict
        '''
        def check_done(_mail_thread, success, message, job):
            result = {"rc"  : success and "0" or "-1",
                      "msg" : message}
            job.set_state("complete", result)

            event = main_events.Event(None,
                                      "%s %s: %s" % (_("Checking mail for"),
                                                     job.get_dest(),
                                                     message))
            self.emit("event", event)


        args = job.get_account() + (job.get_dest(),)

        if args[0] == "@WL2K":
            if self.__config.getboolean("prefs", "msg_allow_wl2k"):
                mail_thread = wl2k.WinLinkThread(self.__config,
                                                 job.get_dest(),
                                                 args[1])
                mail_thread.connect("event", self.__proxy_emit("event"))
                mail_thread.connect("form-received",
                                    self.__proxy_emit("form-received"))
                mail_thread.connect("form-sent", self.__proxy_emit("form-sent"))
            else:
                return {"rc"  : "False",
                        "msg" : "WL2K gateway is disabled"}
        else:
            if self.__config.getboolean("prefs", "msg_allow_pop3"):
                mail_thread = emailgw.CoercedMailThread(self.__config, *args)
            else:
                return {"rc"  : "False",
                        "msg" : "POP3 gateway is disabled"}

        self.emit("register-object", mail_thread)
        mail_thread.connect("mail-thread-complete", check_done, job)
        mail_thread.start()

        event = main_events.Event(None,
                                  "%s %s" % (job.get_dest(),
                                             _("requested a mail check")))
        self.emit("event", event)
        return None
