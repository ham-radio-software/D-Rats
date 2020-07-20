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
import time
import datetime
import os
import glob
import sys

import gobject

from d_rats import ddt2, signals, emailgw, wl2k

# This feels wrong
from d_rats.ui import main_events

from d_rats.sessions import base, stateless
from d_rats.version import DRATS_VERSION
from d_rats.utils import log_exception
#importing printlog() wrapper
from d_rats.debug import printlog

ASCII_FS = "\x1C"
ASCII_GS = "\x1D"
ASCII_RS = "\x1E"
ASCII_US = "\x1F"

class UnknownRPCCall(Exception):
    pass

def encode_dict(source):
    elements = []
    for k, v in source.items():
        if not isinstance(k, str):
            raise Exception("Cannot encode non-string dict key")

        if not isinstance(v, str):
            raise Exception("Cannot encode non-string dict value")

        elements.append(k + ASCII_US + v)
    return ASCII_RS.join(elements)

def decode_dict(string):
    result = {}
    if not string:
        return result
    elements = string.split(ASCII_RS)
    for element in elements:
        try:
            k, v = element.split(ASCII_US)
        except ValueError:
            raise Exception("Malformed dict encoding")
        result[k] = v

    return result

class RPCJob(gobject.GObject):
    __gsignals__ = {
        "state-change" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE,
                          (gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)),
        }

    STATES = ["complete", "timeout", "running"]

    def __init__(self, dest, desc):
        gobject.GObject.__init__(self)
        self.__dest = dest
        self.__desc = desc
        self._args = {}

    def get_dest(self):
        return self.__dest

    def get_desc(self):
        return self.__desc

    def set_state(self, state, result={}):
        if not isinstance(result, dict):
            raise Exception("Value of result property must be dict")
        if state in self.STATES:
            gobject.idle_add(self.emit, "state-change", state, result)
        else:
            raise Exception("Invalid status `%s'" % state)

    def unpack(self, raw):
        self._args = {}
        if not raw:
            self._args = {}
        else:
            self._args = decode_dict(raw)

    def pack(self):
        return encode_dict(self._args)

    def do(self, rpcactions):
        return {"rc" : "Unsupported Job Type"}

class RPCFileListJob(RPCJob):
    def set_file_list(self, list):
        self._args = {}
        for item in list:
            self._args[item] = ""

    def get_file_list(self):
        return list(self._args.keys())

    def do(self, rpcactions):
        return rpcactions.RPC_file_list(self)

class RPCFormListJob(RPCJob):
    def get_form_list(self):
        return []

    def do(self, rpcactions):
        return rpcactions.RPC_form_list(self)

class RPCPullFileJob(RPCJob):
    def set_file(self, filename):
        self._args = {"fn" : filename}

    def get_file(self):
        return self._args.get("fn", None)

    def do(self, rpcactions):
        return rpcactions.RPC_file_pull(self)

class RPCDeleteFileJob(RPCJob):
    def set_file(self, filename):
        self._args["fn"] = filename

    def set_pass(self, passwd):
        self._args["passwd"] = passwd

    def get_file(self):
        return self._args.get("fn", None)

    def get_pass(self):
        return self._args.get("passwd", "")

    def do(self, rpcactions):
        return rpcactions.RPC_file_delete(self)

class RPCPullFormJob(RPCJob):
    def set_form(self, form):
        self._args = {"fn" : form}

    def get_form(self):
        return self._args.get("fn", None)

    def do(self, rpcactions):
        return rpcactions.RPC_form_pull(self)

class RPCPositionReport(RPCJob):
    def set_station(self, station):
        self._args = {"st" : station}

    def get_station(self):
        return self._args.get("st", "ERROR")

    def do(self, rpcactions):
        return rpcactions.RPC_pos_report(self)

class RPCGetVersion(RPCJob):
    def do(self, rpcactions):
        return rpcactions.RPC_get_version(self)

class RPCCheckMail(RPCJob):
    def do(self, rpcactions):
        return rpcactions.RPC_check_mail(self)

    def set_account(self, host, user, pasw, port, ssl):
        self._args = {"host" : host,
                      "user" : user,
                      "pasw" : pasw,
                      "port" : port,
                      "ssl"  : ssl,
                      }

    def get_account(self):
        return self._args["host"], self._args["user"], self._args["pasw"], \
            int(self._args["port"]), self._args["ssl"] == "True"

class RPCSession(gobject.GObject, stateless.StatelessSession):
    type = base.T_RPC

    T_RPCREQ = 0
    T_RPCACK = 1

    def __init__(self, *args, **kwargs):
        gobject.GObject.__init__(self)

        try:
            self.__rpcactions = kwargs["rpcactions"]
            del kwargs["rpcactions"]
        except KeyError:
            raise Exception("RPCSession requires RPCActionSet")

        stateless.StatelessSession.__init__(self, *args, **kwargs)
        self.__jobs = {}
        self.__jobq = []
        self.__jobc = 0
        self.__t_retry = 30
        self.__enabled = True

        gobject.timeout_add(1000, self.__worker)

        self.handler = self.incoming_data

    def notify(self):
        pass

    def __decode_rpccall(self, frame):
        jobtype, args = frame.data.split(ASCII_GS)
        # FIXME: Make this more secure
        if not (jobtype.isalpha() and jobtype.startswith("RPC")):
            raise UnknownRPCCall("Unknown call `%s'" % jobtype)

        job = eval("%s('%s', 'New job')" % (jobtype, frame.s_station))
        job.unpack(args)
        
        return job

    def __encode_rpccall(self, job):
        return "%s%s%s" % (job.__class__.__name__, ASCII_GS, job.pack())

    def __get_seq(self):
        self.__jobc += 1
        return self.__jobc

    def __job_to_frame(self, job, id):
        frame = ddt2.DDT2EncodedFrame()
        frame.type = self.T_RPCREQ
        frame.seq = id
        frame.data = self.__encode_rpccall(job)
        frame.d_station = job.get_dest()
            
        return frame

    def __send_job_status(self, id, station, state, result):
        frame = ddt2.DDT2EncodedFrame()
        frame.type = self.T_RPCACK
        frame.seq = id
        frame.data = result
        frame.d_station = station

        return frame

    def __job_state(self, job, state, _result, id):
        printlog("RPC","       : Job state: %s for %i: %s" % (state, id, _result))

        if state == "running":
            return

        result = encode_dict(_result)
        f = self.__send_job_status(id, job.get_dest(), state, result)
        self._sm.outgoing(self, f)

    def incoming_data(self, frame):
        if frame.type == self.T_RPCREQ:
            try:
                job = self.__decode_rpccall(frame)
            except UnknownRPCCall as e:
                printlog("RPC","       : incoming data : unable to execute RPC from %s: %s" % (frame.s_station, e))
                return

            job.connect("state-change", self.__job_state, frame.seq)
            result = job.do(self.__rpcactions)
            if result is not None:
                job.set_state("complete", result)

        elif frame.type == self.T_RPCACK:
            if frame.seq in self.__jobs:
                ts, att, job = self.__jobs[frame.seq]
                del self.__jobs[frame.seq]
                job.set_state("complete", decode_dict(frame.data))
            else:
                printlog("RPC","       : incoming data : Unknown job %i" % frame.seq)

        else:
            printlog("RPC","       : incoming data : Unknown RPC frame type %i" % frame.type)

    def __send_job(self, job, id):
        printlog("RPC","       : Sending job `%s' to %s" % (job.get_desc(), job.get_dest()))
        frame = self.__job_to_frame(job, id)
        job.frame = frame
        self._sm.outgoing(self, frame)
        printlog("RPC","       : Job sent")

    def __worker(self):
        for id, (ts, att, job) in self.__jobs.items():
            if job.frame and not job.frame.sent_event.isSet():
                # Reset timer until the block is sent
                self.__jobs[id] = (time.time(), att, job)
            elif (time.time() - ts) > self.__t_retry:
                printlog("RPC","       : Cancelling job %i due to timeout" % id)
                del self.__jobs[id]
                job.set_state("timeout")

        return True

    def submit(self, job):
        id = self.__get_seq()
        self.__send_job(job, id)
        self.__jobs[id] = (time.time(), 0, job)

    def stop(self):
        self.__enabled = False

class RPCActionSet(gobject.GObject):
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
        self.__config = config
        self.__port = port

        gobject.GObject.__init__(self)

    def __proxy_emit(self, signal):
        def handler(obj, *args):
            printlog("RPC","       : Proxy emit %s: %s" % (signal, args))
            gobject.idle_add(self.emit, signal, *args)

        return handler

    def RPC_pos_report(self, job):
        result = {}
        mycall = self.__config.get("user", "callsign")
        rqcall = job.get_station()
        
        printlog("RPC","       : Position request for `%s'" % rqcall)
        printlog("RPC","      : Self=%s" % format(self))

        if rqcall == mycall or rqcall == ".":
            rqcall = None
        try:
            #obtaining current position from config or local gps
            fix = self.emit("get-current-position", rqcall)
            #result = fix.to_NMEA_GGA()
            result["rc"] = "True"
            result["msg"] = fix.to_APRS(symtab=self.__config.get("settings", "aprssymtab"),
                               symbol=self.__config.get("settings", "aprssymbol"))
            
        except Exception as e:
            printlog("RPC","       : Case KO : Exception while getting position of %s: " % rqcall)
            log_exception()
            fix = None
            result["rc"] = "False"
            result["msg"] = " No data for station '%s'" % job.get_station()

        if fix:
            #sending the position to transport // but this is broken!!
            printlog("RPC","       : port is           : %s" % self.__port)
            printlog("RPC","       : fix is            : %s" % fix)
            printlog("RPC","       : fix in NMEA GGA is: %s" % fix.to_NMEA_GGA())
            printlog("RPC","       : fix in APRS is: %s" % result)
            
            #self.emit("user-send-chat","CQCQCQ", self.__port, fix.to_NMEA_GGA(), True)            
            self.emit("user-send-chat",
                      "CQCQCQ", 
                      self.__port, 
                      result["msg"],
                      True)
        return None
            
    def RPC_file_list(self, job):
        result = {}
    
        dir = self.__config.get("prefs", "download_dir")
        files = glob.glob(os.path.join(dir, "*.*"))
        for fn in files:
            if os.path.isdir(fn):
                continue
            size = os.path.getsize(fn)
            if size < 1024:
                units = "B"
            else:
                size >>= 10
                units = "KB"
    
            ds = datetime.datetime.fromtimestamp(os.path.getmtime(fn))
    
            fn = os.path.basename(fn)
            result[fn] = "%i %s (%s)" % (size,
                                         units,
                                         ds.strftime("%Y-%m-%d %H:%M:%S"))
    
        event = main_events.Event(None, job.get_dest() + " " + \
                                      _("Requested file list"))
        self.emit("event", event)

        return result
    
    def RPC_form_list(self, job):
        result = {}
        forms = self.emit("get-message-list", "CQCQCQ")
        for subj, stamp, filen in forms:
            ts = time.localtime(stamp)
            result[filen] = "%s/%s" % (subj,
                                       time.strftime("%b-%d-%Y %H:%M:%S", ts))
    

        event = main_events.Event(None, job.get_dest() + " " + \
                                      _("Requested message list"))
        self.emit("event", event)

        return result
    
    def RPC_file_pull(self, job):
        result = {}
    
        if not self.__config.getboolean("prefs", "allow_remote_files"):
            result["rc"] = "Remote file transfers not enabled"
            return result

        dir = self.__config.get("prefs", "download_dir")
        path = os.path.join(dir, job.get_file())
        printlog("RPC","      : Remote requested %s" % path)
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
    
    def RPC_file_delete(self, job):
        result = {}

        _permlist = self.__config.get("settings", "delete_from")
        try:
            permlist = _permlist.upper().split(",")
        except Exception:
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
        except Exception as e:
            result["rc"] = "Unable to delete %s: %s" % (job.get_file(), e)
        return result

    def RPC_form_pull(self, job):
        result = {}
    
        forms = self.emit("get-message-list", "CQCQCQ")
        result["rc"] = "Form not found"
        for subj, stamp, filen in forms:
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

    def RPC_get_version(self, job):
        result = {}

        result["version"] = DRATS_VERSION
        result["os"] = self.__config.platform.os_version_string()
        result["pyver"] = ".".join([str(x) for x in sys.version_info[:3]])
        try:
            import gtk
            result["pygtkver"] = ".".join([str(x) for x in gtk.pygtk_version])
            result["gtkver"] = ".".join([str(x) for x in gtk.gtk_version])
        except ImportError:
            result["pygtkver"] = result["gtkver"] = "Unknown"
            printlog("RPC","       : RPC_get_version: %s" % result)
            
        return result

    def RPC_check_mail(self, job):
        def check_done(mt, success, message, job):
            result = { "rc"  : success and "0" or "-1",
                       "msg" : message }
            job.set_state("complete", result)

            event = main_events.Event(None,
                                      "%s %s: %s" % (_("Checking mail for"),
                                                     job.get_dest(),
                                                     message))
            self.emit("event", event)


        args = job.get_account() + (job.get_dest(),)

        if args[0] == "@WL2K":
            if self.__config.getboolean("prefs", "msg_allow_wl2k"):
                mt = wl2k.WinLinkThread(self.__config,
                                        job.get_dest(),
                                        args[1])
                mt.connect("event", self.__proxy_emit("event"))
                mt.connect("form-received", self.__proxy_emit("form-received"))
                mt.connect("form-sent", self.__proxy_emit("form-sent"))
            else:
                return {"rc"  : "False",
                        "msg" : "WL2K gateway is disabled"}
        else:
            if self.__config.getboolean("prefs", "msg_allow_pop3"):
                mt = emailgw.CoercedMailThread(self.__config, *args)
            else:
                return {"rc"  : "False",
                        "msg" : "POP3 gateway is disabled"}

        self.emit("register-object", mt)
        mt.connect("mail-thread-complete", check_done, job)
        mt.start()

        event = main_events.Event(None,
                                  "%s %s" % (job.get_dest(),
                                             _("requested a mail check")))
        self.emit("event", event)
