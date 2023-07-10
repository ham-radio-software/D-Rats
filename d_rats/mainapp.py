'''mainapp'''
# pylint wants only 1000 lines
# pylint: disable=too-many-lines
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# review 2015 Maurizio Andreotti  <iz2lxi@yahoo.it>
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

from configparser import NoOptionError
import logging
import os
import sys

# this to generate timestamps associated to GPS fixes
from time import gmtime, strftime
# import various libraries of support functions
import time
import socket

import glob
import shutil

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk          # to manage windows objects
from gi.repository import Gio
from gi.repository import GObject      # to manage multitasking
from gi.repository import GLib

from .dplatform import Platform
from .aprs_icons import APRSicons

logging.basicConfig(level=logging.INFO)

MAINAPP_LOGGER = logging.getLogger("Mainapp")

# This code is assuming that mainapp is only imported in d-rats
# This needs to be moved to later, but before the first message is written.
# The also needs to be integrated into the logging module.
DEBUG_PATH = Platform.get_platform().config_file("debug.log")
if sys.platform == "win32" or not os.isatty(0):
    sys.stdout = open(DEBUG_PATH, "w")
    sys.stderr = sys.stdout
    MAINAPP_LOGGER.info("Enabled debug log for Win32 systems")
else:
    try:
        os.unlink(DEBUG_PATH)
    except OSError:
        pass

# load the basic d-rats labels - it will load the localized translation later
# gettext.install("D-RATS")

# these modules are imported from the d_rats folder
from . import mainwindow
from . import config
from . import gps
from . import map as Map
from . import map_sources
from . import comm
from . import sessionmgr
from . import session_coordinator
from . import formgui
from . import station_status
from . import pluginsrv
from . import msgrouting
from . import wl2k
from . import version
from . import mailsrv

from .emailgw import PeriodicAccountMailThread
from .emailgw import AccountMailThread
from .emailgw import validate_incoming
from .emailgw import EmailGatewayException
from .aprs_dprs import AprsDprsCodes
from .dratsexception import DPRSInvalidCode
from .ui import main_events
from .ui.main_common import prompt_for_station

from .utils import NetFile
from .sessions import rpc, chat, sniff

# gettext module provides message translation and catalog management
# normally we would just set a default here, but we need to fix the
# issue that mainapp is imported by multiple modules first.
if not '_' in locals():
    import gettext
    _ = gettext.gettext

# lets init the basic functions of the mainapp module
LOGTF = "%m-%d-%Y_%H:%M:%S"
MAINAPP = None

# initialize the multitasking for gtk (required to manage events in gtk
# windows and background activities)
# Documentation indicates that this should not be done this way.
GObject.threads_init()


class MainappException(Exception):
    '''Generic Mainapp Exception.'''


class MainappFileOpenError(MainappException):
    '''Unable to open a file.'''


class MainappExecError(MainappException):
    '''Failed to exec command.'''


class MainappConfigCanceled(MainappException):
    '''Configuration Cancelled.'''


class MainappPortStartedError(MainappException):
    '''Port already started.'''


class MainappStationNotFound(MainappException):
    '''Station not found.'''


def ping_file(filename):
    '''
    Ping file.

    Checks if the file passed as parameter can be opened.

    :param filename: Filename to test open
    :type filename: str
    :raises: :class:`MainappFileOpenError` if unable to open file
    :returns: File data
    :rtype: bytes
    '''
    try:
        fhandle = NetFile(filename, "r")
    except IOError as err:
        # pylint: disable=raise-missing-from
        raise MainappFileOpenError("Unable to open file %s: %s" %
                                   (filename, err))

    data = fhandle.read()
    fhandle.close()

    return data


def ping_exec(command):
    '''
    Ping exec

    Checks if the command passed as parameter can be opened

    :param command: Command to try
    :type command: str
    :raises: MainappExecError if the ping fails.
    :returns: Output of command
    :rtype: str
    '''
    pform = Platform.get_platform()
    scmd, ocmd = pform.run_sync(command)
    if scmd:
        raise MainappExecError("Failed to run command: %s" % command)
    return ocmd


class CallList():
    '''
    Seen Call List.

    This class is updated with seen stations.
    I can not find anything using this data.
    '''

    def __init__(self):
        self.logger = logging.getLogger("CallList")
        self.clear()

    def clear(self):
        '''Clear call list data.'''
        self.data = {}

    def set_call_pos(self, call, pos):
        '''
        Set call position.

        No reference to this method found.

        :param call: Call sign
        :type call: str
        :param pos: Position
        :type pos: unknown
        '''
        (call_time, _) = self.data.get(call, (0, None))

        self.data[call] = (call_time, pos)

    def set_call_time(self, call, tset=None):
        '''
        Set call time.

        :param call: Callsign
        :type call: str
        :param tset: Time to set
        :type tset: float
        '''
        if tset is None:
            tset = time.time()

        (_, pos) = self.data.get(call, (0, None))

        self.data[call] = (tset, pos)

    def get_call_pos(self, call):
        '''
        Get call position.

        No reference to this method found.

        :param call: Call sign
        :type call: str
        :returns: Position
        :rtype: unknown
        '''
        (_, pos) = self.data.get(call, (0, None))
        return pos

    def get_call_time(self, call):
        '''
        Get call time.

        No reference to this method found.

        :param call: Call sign
        :type call: str
        :returns: Time call sign was heard
        :rtype: float
        '''
        (call_time, _) = self.data.get(call, (0, None))
        return call_time

    def list(self):
        '''
        List Calls.

        :returns: Known call signs
        :rtype: list[str]
        '''
        return list(self.data.keys())

    def is_known(self, call):
        '''
        Is known call.

        :param call: Callsign to lookup
        :type call: str
        :returns: If call sign is known
        :rtype: bool
        '''
        return call in self.data

    def remove(self, call):
        '''
        Remove call.

        :param call: Call sign
        :type call: str
        '''
        try:
            del self.data[call]
        except KeyError:
            pass


# pylint wants a maximum of 7 instance attributes
# pylint: disable=too-many-instance-attributes
class MainApp(Gtk.Application):
    '''
    Main App.

    :param __args: Not used, Ignored
    '''

    def __init__(self, **_args):
        Gtk.Application.__init__(self,
                                 application_id='localhost.d-rats',
                                 flags=Gio.ApplicationFlags.NON_UNIQUE)

        self.logger = logging.getLogger("MainApp")
        self.handlers = {
            "status" : self.__status,
            "user-stop-session" : self.__user_stop_session,
            "user-cancel-session" : self.__user_cancel_session,
            "user-send-form" : self.__user_send_form,
            "user-send-file" : self.__user_send_file,
            "rpc-send-form" : self.__user_send_form,
            "rpc-send-file" : self.__user_send_file,
            "user-send-chat" : self.__user_send_chat,
            "incoming-chat-message" : self.__incoming_chat_message,
            "outgoing-chat-message" : self.__outgoing_chat_message,
            "get-station-list" : self.__get_station_list,
            "get-message-list" : self.__get_message_list,
            "submit-rpc-job" : self.__submit_rpc_job,
            "event" : self.__event,
            "notice" : False,
            "config-changed" : self.__config_changed,
            "show-map-station" : self.__show_map_station,
            "ping-station" : self.__ping_station,
            "ping-station-echo" : self.__ping_station_echo,
            "ping-request" : self.__ping_request,
            "ping-response" : self.__ping_response,
            "incoming-gps-fix" : self.__incoming_gps_fix,
            "station-status" : self.__station_status,
            "get-current-status" : self.__get_current_status,
            "get-current-position" : self.__get_current_position,
            "session-status-update" : self.__session_status_update,
            "session-started" : self.__session_started,
            "session-ended" : self.__session_ended,
            "file-received" : self.__file_received,
            "form-received" : self.__form_received,
            "file-sent" : self.__file_sent,
            "form-sent" : self.__form_sent,
            "get-chat-port" : self.__get_chat_port,
            "trigger-msg-router" : self.__trigger_msg_router,
            "register-object" : self.__register_object,
            }

        # pylint: disable=global-statement
        global MAINAPP
        MAINAPP = self

        self.comm = None
        self.active_sessions = {}
        self.seen_callsigns = CallList()
        self.position = None
        self.mail_threads = {}
        self.mainwindow = None
        self.__unused_pipes = {}
        self.__pipes = {}
        self.pop3srv = None
        self.msgrouter = None
        self.plugsrv = None
        self.stations_overlay = None
        self.__map_point = None
        self.connect("shutdown", self.ev_shutdown)
        self.default_comment = None

        self.config = config.DratsConfig(self)
        self._refresh_lang()

        self._announce_self()

        message = _("Since this is your first time running D-RATS, " +
                    "you will be taken directly to the configuration " +
                    "dialog.  At a minimum, put your callsign in the " +
                    "box and click 'Save'.  You will be connected to " +
                    "the ratflector initially for testing.")

        # if user callsign is not present, ask the user to fill in the
        # basic info
        while self.config.get("user", "callsign") == "":
            dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK)
            dialog.set_markup(message)
            dialog.run()
            dialog.destroy()
            if not self.config.show():
                raise MainappConfigCanceled("User canceled configuration")
            message = _("You must enter a callsign to continue")

        # load position from config
        self.logger.info("load position from config file")
        self.gps = self._static_gps()

        self.map = None

    def callback_gps(self, lat, lng, station="", comments=""):
        '''
        Callback GPS

        This is to communicate the gps fixes to the D-Rats Web Map
        standalone program load server ip and port.

        :param lat: Latitude
        :type lat: float
        :param lng: Longitude
        :type lng: float
        :param station: Station, default ""
        :type station: str
        :param comments: Comments, default ""
        :type comments: float
        '''
        mapserver_ip = self.config.get("settings", "mapserver_ip")
        mapserver_port = int(self.config.get("settings", "mapserver_port"))

        # this method broadcasts the gps fixes to a GPS server
        flat = float(lat)
        flng = float(lng)

        # Prepare string to broadcast to internet browsers clients
        message_str = '{ "lat": "%f", "lng": "%f", "station": "%s", ' \
                      '"comments": "%s","timestamp": "%s"  }' \
                      % (flat, flng, station, comments,
                         strftime("%Y-%m-%d %H:%M:%S", gmtime()))
        message = message_str.encode("utf-8", 'replace')
        self.logger.info("preparing our gps fix in JSON :%s", message)

        try:
            # create an AF_INET, STREAM socket (TCP)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error:
            self.logger.info("Failed to create socket.", exc_info=True)
            # Tolerate map server not being up.
            return
        self.logger.info("Socket Created")

        # Connect to remote server
        self.logger.info("Connecting to: %s:%s",
                         mapserver_ip, mapserver_port)
        try:
            # create an AF_INET, STREAM socket (TCP)
            sock.connect((mapserver_ip, mapserver_port))

            self.logger.info("message to send: %s", message)
            try:
                # Set the whole string
                sock.sendall(message)
                sock.close()
            except socket.error:
                # Send failed
                self.logger.info("Send failed of: %s", message, exc_info=True)
                return

            self.logger.info("Message sent successfully")
            return

        except socket.error:
            self.logger.info("Failed to create socket.", exc_info=True)
            sock.close()
            sock = None
            return

    # pylint does not grok all gtk methods.
    # pylint: disable=arguments-differ
    def do_activate(self):
        '''
        Do Activation.

        Emits a :class:`Gio.Application` signal to the application.
        '''
        self.logger.info("load main window with self config")
        self.mainwindow = mainwindow.MainWindow(self)

        try:
            self.plugsrv = pluginsrv.DRatsPluginServer()
            self.__connect_object(self.plugsrv.get_proxy())
            self.plugsrv.serve_background()

        except (ConnectionError, OSError) as err:
            self.logger.info("Unable to start plugin server: %s", err)
            self.plugsrv = None

        self.load_static_routes()

        try:
            self.msgrouter = msgrouting.MessageRouter(self.config, self,
                                                      validate_incoming)
            self.__connect_object(self.msgrouter)
            self.msgrouter.start()
        except TypeError:
            self.logger.info("Main: MessageRouter setup failed!",
                             exc_info=True)
            self.msgrouter = None

        self.logger.info("connect main window")
        self.__connect_object(self.mainwindow)
        self.logger.info("connect tabs")
        for tab in self.mainwindow.tabs.values():
            self.__connect_object(tab)

        if self.config.getboolean("prefs", "dosignon") and self.chat_session:
            self.logger.info("going online")
            msg = self.config.get("prefs", "signon")
            status = station_status.STATUS_ONLINE
            for port in self.active_sessions:
                self.chat_session(port).advertise_status(status, msg)
        GLib.timeout_add(3000, self._refresh_location)

        # create map instance
        self.logger.info("create map window object-----")
        self.map = Map.Window(self, self.config)
        self.map.set_title("D-RATS Map Window - map in use: %s" %
                           self.config.get("settings", "maptype"))
        self.map.connect("reload-sources", lambda m: self._load_map_overlays())
        self.logger.info("create map window object: connect object-----")
        self.__connect_object(self.map)

        self.logger.info("query local gps device to see our current position")
        pos = self.get_position()
        self.map.set_center(pos.latitude, pos.longitude)
        self.map.set_zoom(14)
        self._load_map_overlays()
        self.logger.info("invoke config refresh")
        self.refresh_config()
        Gtk.Application.do_activate(self)

    def do_quit_mainloop(self):
        '''Do Quit Main Loop.'''
        # Temp for debugging
        print("mainapp/do_quit_mainloop")
        Gtk.Application.do_quit_mainloop(self)

    def do_shutdown(self):
        '''Do Shutdown.'''
        # Temp for debugging
        print("mainapp/do_shutdown")
        Gtk.Application.do_shutdown(self)

    @staticmethod
    def ev_shutdown(application):
        '''
        Event Shutdown Handler.

        This is needed to signal all child activities that the application
        is shutting down, in case some activities such as the map module
        normally only hide their window on shutdown.

        Signaled when all holders of a reference to a widget should release
        the reference that they hold.

        May result in finalization of the widget if all references are released
        Any return value usage not documented in Gtk 3

        :param application: Application instance
        :type application: :class:`Gtk.Application`
        '''
        # temp for debugging
        print("mainapp/ev_shutdown")
        if application.map:
            application.map.exiting = True

    def stop_comms(self, portid):
        '''
        Stop communications.

        :param portid: Port id for communications
        :returns: True if all communication is stopped.
        :rtype: bool
        '''
        if portid in self.active_sessions:
            smgr, scomm = self.active_sessions[portid]
            smgr.shutdown(True)
            scomm.shutdown()
            del self.active_sessions[portid]

            portspec, pipe = self.__pipes[portid]
            del self.__pipes[portid]
            self.__unused_pipes[portspec] = pipe

            return True
        return False

    def _make_socket_listeners(self, sconn):
        '''
        Make socket listeners.

        :param sconn: Session Connection
        :type sconn: :class:`session_coordinator.SessionCoordinator`
        '''
        forwards = self.config.options("tcp_out")
        for forward in forwards:
            try:
                sport, dport, station = \
                    self.config.get("tcp_out", forward).split(",")
                sport = int(sport)
                dport = int(dport)
            except (NoOptionError, ValueError):
                self.logger.info("Failed to parse TCP forward config %s",
                                 forward)
                return

            try:
                sconn.create_socket_listener(sport, dport, station)
                self.logger.info("Started socket listener %i:%i@%s",
                                 sport, dport, station)
            except session_coordinator.ListenerActiveError:
                self.logger.info(
                    "Failed to start socket listener %i:%i@%s:",
                    sport, dport, station)

    # pylint wants a maximum of 15 local variables
    # pylint wants a maximum of 12 branches
    # pylint wants a maximum of 50 statements
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    def start_comms(self, portid):
        '''
        Start communications.

        :param portid: Port ID for communications
        :type portid: str
        :raises: :class:`MainappPortStartedError`: if the port can not
                 be started
        '''
        self.logger.info("Starting Comms")
        # load from the "ports" config the line related to portid
        spec = self.config.get("ports", portid)
        try:
            # try getting the config params from splitting the config line
            enb, port, rate, dosniff, raw, name = spec.split(",")
            enb = (enb == "True")          # means port is enabled
            dosniff = (dosniff == "True")  # means traffic sniffing to be active
            raw = (raw == "True")          # means raw to be active
        except ValueError:
            self.logger.info("Start_comms: Failed to parse portspec %s",
                             spec, exc_info=True)
            return

        if not enb:
            # if port not enabled, and was already active, let's cancel it
            if name in self.active_sessions:
                del self.active_sessions[name]
            return

        self.logger.info("start_comms: Starting port %s (%s)", portid, name)

        call = self.config.get("user", "callsign")

        if port in self.__unused_pipes:
            path = self.__unused_pipes[port]
            del self.__unused_pipes[port]
            self.logger.info("start_comms: Re-using path %s for port %s",
                             path, port)
        elif port.startswith("tnc-ax25:"):
            self.logger.info("start_comms: Port %s as tnc-ax25", port)
            _tnc, _port, tncport, path = port.split(":")
            path = path.replace(";", ",")
            _port = "%s:%s" % (_port, tncport)
            path = comm.TNCAX25DataPath((_port, int(rate), call, path))
        elif port.startswith("tnc:"):
            _port = port.replace("tnc:", "")
            path = comm.TNCDataPath((_port, int(rate)))
        elif port.startswith("dongle:"):
            path = comm.SocketDataPath(("127.0.0.1", 20003, call, None))
        elif port.startswith("agwpe:"):
            path = comm.AGWDataPath(port, 0.5)
            self.logger.info("start_comms: Opening AGW: %s", path)
        elif ":" in port:
            try:
                (_mode, host, sport) = port.split(":")
            except ValueError:
                event = main_events.Event(None,
                                          _("Failed to connect to") + \
                                              " %s: " % port + \
                                              _("Invalid port string"))
                self.mainwindow.tabs["event"].event(event)
                return

            path = comm.SocketDataPath((host, int(sport), call, rate))
        else:
            path = comm.SerialDataPath((port, int(rate)))

        if name in self.__pipes:
            raise MainappPortStartedError("Port %s already started!" % name)
        self.__pipes[name] = (port, path)

        def transport_msg(msg):
            _port = name
            event = main_events.Event(None, "%s: %s" % (_port, msg))
            GLib.idle_add(self.mainwindow.tabs["event"].event, event)

        transport_args = {
            "compat" : raw,
            "warmup_length" : self.config.getint("settings", "warmup_length"),
            "warmup_timeout" : self.config.getint("settings", "warmup_timeout"),
            "force_delay" : self.config.getint("settings", "force_delay"),
            "msg_fn" : transport_msg,
            }

        if name not in self.active_sessions:
            # if we are not chatting 1-to-1 let's do CQ
            smgr = sessionmgr.SessionManager(path, call, **transport_args)

            chat_session = smgr.start_session("chat",
                                              dest="CQCQCQ",
                                              cls=chat.ChatSession)
            self.__connect_object(chat_session, name)

            rpcactions = rpc.RPCActionSet(self.config, name)
            self.__connect_object(rpcactions)

            _rpc_session = smgr.start_session("rpc",
                                              dest="CQCQCQ",
                                              cls=rpc.RPCSession,
                                              rpcactions=rpcactions)

            def sniff_event(_sstart, src, _dst, msg, port):
                '''
                Sniff Event Handler.

                :param _sstart: Sniff Session
                :type __sstart: :class:`sniff.SniffSession`
                :param src: Source station
                :type src: str
                :param _dst: Destination station
                :type _dst: str
                :param msg: Message
                :type msg: bytes
                :param port: Radio port
                :type port: str
                '''
                # here print the sniffed traffic into the event tab
                if dosniff:
                    event = main_events.Event(None, "Sniffer: %s" % msg)
                    self.mainwindow.tabs["event"].event(event)

                # in any case let's print the station heard into stations tab
                self.mainwindow.tabs["stations"].saw_station(src, port)

            sses = smgr.start_session("Sniffer",
                                      dest="CQCQCQ",
                                      cls=sniff.SniffSession)
            # pylint: disable=protected-access
            smgr.set_sniffer_session(sses._id)
            sses.connect("incoming_frame", sniff_event, name)

            scoord = session_coordinator.SessionCoordinator(self.config, smgr)
            self.__connect_object(scoord, name)

            smgr.register_session_cb(scoord.session_cb, None)

            self._make_socket_listeners(scoord)

            self.active_sessions[name] = smgr, scoord

            pingdata = self.config.get("settings", "ping_info")
            if pingdata.startswith("!"):
                def pingfn():
                    return ping_exec(pingdata[1:])
            elif pingdata.startswith(">"):
                def pingfn():
                    return ping_file(pingdata[1:])
            elif pingdata:
                def pingfn():
                    return pingdata
            else:
                pingfn = None
            chat_session.set_ping_function(pingfn)
        else:
            smgr, _sc = self.active_sessions[name]

            smgr.set_comm(path, **transport_args)
            smgr.set_call(call)
        return

    def chat_session(self, portname):
        '''
        Chat session.

        :param portname: Port name for session
        :type portname: str
        :returns: Chat Session object
        :rtype: :class:`sessions.chat.ChatSession`
        '''
        return self.active_sessions[portname][0].get_session(lid=1)

    def rpc_session(self, portname):
        '''
        RPC session.

        :param portname: Port name for session
        :type portname: str
        :returns: RPC Session object
        '''
        return self.active_sessions[portname][0].get_session(lid=2)

    def session_coordinator(self, portname):
        '''
        Session Coordinator.

        :param portname: Port name for session
        :type portname: str
        :returns: Session Coordinator for port name
        :rtype: :class:`session_coordinator.SessionCoordinator`
        '''
        return self.active_sessions[portname][1]

    def check_comms_status(self):
        '''Check communication statuses.'''
        # added in 0.3.10
        self.logger.info(
            "check_comms_status: Ports expected to be already started:")
        for portid in self.active_sessions:
            self.logger.info("check_comms_status: %s", portid)

        self.logger.info("check_comms_status: Checking all Ports from config:")
        for portid in self.config.options("ports"):
            self.logger.info("check_comms_status: portid %s", portid)

            # load from the "ports" config the line related to portid
            spec = self.config.get("ports", portid)
            try:
                # try getting the config params from splitting the config line
                enb, _port, _rate, dosniff, raw, name = spec.split(",")
                enb = (enb == "True")           # means port is enabled
                dosniff = (dosniff == "True")   # means traffic sniffing to be
                                                # active
                raw = (raw == "True")           # means raw to be active
            except ValueError:
                self.logger.info(
                    "check_comms_status: Failed to parse portspec %s",
                    spec, exc_info=True)

            if name in self.__pipes:
                self.logger.info("check_comms_status: Port %s already started!",
                                 name)
            else:
                self.logger.info("check_comms_status: Port %s not started",
                                 name)

    def check_stations_status(self):
        '''
        Check stations status.
        '''
        # wb8tyw: Can not find anything calling this.
        # added in 0.3.10
        self.logger.info("Check stations Status")
        station_list = self.emit("get-station-list")
        stations = []
        for portlist in station_list.values():
            stations += [str(x) for x in portlist]
            station, port = prompt_for_station(stations, self.config)
            self.logger.info(
                "check_stations_status: Stations %s resulting on port %s",
                station, port)

    def _refresh_comms(self):
        '''Refresh communications.'''
        delay = False
        self.logger.info("refresh comms")

        for portid in list(self.active_sessions):
            self.logger.info("_refresh_comms: Stopping %s", portid)
            if self.stop_comms(portid):
                if sys.platform == "win32":
                    # Wait for windows to let go the serial port
                    delay = True

        if delay:
            time.sleep(0.25)

        for portid in self.config.options("ports"):
            self.logger.info("_refresh_comms: Re-Starting %s", portid)
            self.start_comms(portid)

        for spec, path in self.__unused_pipes.items():
            self.logger.info(
                "_refresh_comms: Path %s for port %s no longer needed",
                path, spec)
            path.disconnect()

        self.__unused_pipes = {}

        # added in 0.3.10
        # checking status
        self.check_comms_status()
        # self.check_stations_status()

    def _static_gps(self):
        '''
        Static GPS Coordinates.

        :returns: GPS coordinates
        :rtype: :class:`StaticGPSSource`
        '''
        # initialize the variables to store our local position data fetched
        # from configuration
        lat = 0.0
        lon = 0.0
        alt = 0.0
        call = ""

        try:
            # load static data from configuration
            lat = self.config.get("user", "latitude")
            lon = self.config.get("user", "longitude")
            alt = self.config.get("user", "altitude")
            call = self.config.get("user", "callsign")
            mapserver_active = self.config.get("settings", "mapserver_active")

        except NoOptionError:
            self.logger.info(
                "_static_gps: Invalid static position",
                err_info=True, stack_info=True)

        self.logger.info("_static_gps: Configuring the Static position: %s,%s",
                         lat, lon)

        # Call the mapserver to update our position sweeper
        if mapserver_active == "True":
            self.logger.info("_static_gps: Mapserver active: %s ca;; %s",
                             mapserver_active, call)
            self.callback_gps(lat, lon, call, "altitude: " + alt)
        else:
            self.logger.info(
                "_static_gps: Mapserver not active: %s, call: %s",
                mapserver_active, call)
        return gps.StaticGPSSource(lat, lon, alt)

    def _refresh_gps(self):
        '''Refresh gps.'''
        port = self.config.get("settings", "gpsport")
        rate = self.config.getint("settings", "gpsportspeed")
        enab = self.config.getboolean("settings", "gpsenabled")

        self.logger.info("_refresh_gps : GPS: %s on %s@%i", enab, port, rate)

        if enab:
            if self.gps:
                self.gps.stop()

            if port.startswith("net:"):
                self.gps = gps.NetworkGPSSource(port)
            else:
                self.gps = gps.GPSSource(port, rate)
            self.gps.start()
        else:
            if self.gps:
                self.gps.stop()

            self.gps = self._static_gps()

    def _refresh_mail_threads(self):
        '''Refresh mail threads.'''
        for key, value in self.mail_threads.copy().items():
            value.stop()
            del self.mail_threads[key]

        accts = self.config.options("incoming_email")
        for acct in accts:
            data = self.config.get("incoming_email", acct)
            if data.split(",")[-1] != "True":
                continue
            try:
                mthread = PeriodicAccountMailThread(self.config, acct)
            except EmailGatewayException:
                self.logger.info("Refresh mail threads: broad-except",
                                 exc_info=True)
                continue

            self.__connect_object(mthread)
            mthread.start()
            self.mail_threads[acct] = mthread

        if self.config.getboolean("settings", "msg_smtp_server"):
            try:
                smtpsrv = mailsrv.DratsSMTPServerThread(self.config)
                smtpsrv.start()
                self.mail_threads["SMTPSRV"] = smtpsrv
            except OSError:
                self.logger.info("_refresh_mail_threads: "
                                 "Unable to start SMTP server", exc_info=True)

        if self.config.getboolean("settings", "msg_pop3_server"):
            try:
                pop3srv = mailsrv.DratsPOP3ServerThread(self.config)
                pop3srv.start()
                self.mail_threads["POP3SRV"] = pop3srv
            except OSError:
                self.logger.info("_refresh_mail_threads: "
                                 "Unable to start POP3 server", exc_info=True)

    def _refresh_lang(self):
        '''Refresh Language.'''
        # load the localized labels
        locales = {"Dutch" : "nl",
                 "English" : "en",
                  "German" : "de",
                 "Italian" : "it",
                 "Spanish" : "es",
                   }
        locale = locales.get(self.config.get("prefs", "language"), "English")
        self.logger.info("_refresh_lang: xxx Setting locale to: %s", locale)

        localedirfromconfig = os.path.join(Platform.get_platform().sys_data(),
                                 "locale")
        self.logger.info("_refresh_lang: Setting localedirfromconfig to: %s", localedirfromconfig)

        if "LANGUAGE" not in os.environ:
            os.environ["LANGUAGE"] = locale

        self.logger.info("_refresh_lang: OS Locale set to: %s", os.environ["LANGUAGE"])
        try:
            # This global statement is needed for internationalization
            # pylint: disable=global-statement
            global _
            lang = gettext.translation("D-RATS",
                                       localedir=localedirfromconfig,
                                       languages=[locale])
            lang.install()
            _ = lang.gettext
            #Gtk.glade.bindtextdomain("D-RATS", localedirfromconfig)
            #Gtk.glade.textdomain("D-RATS")
        except FileNotFoundError: 
            #pylint: disable=logging-too-many-args
            self.logger.error("_refresh_lang: Messages catalog file missing ",
                              " for %s.  Need to use 'msgfmt tool to generate.",
                              locale)
            gettext.install("D-RATS")
            _ = gettext.gettext
        except LookupError:
            self.logger.error("_refresh_lang: Unable to load language `%s'",
                              locale, exc_info=True)
            gettext.install("D-RATS")
            _ = gettext.gettext
        except IOError:
            self.logger.error("_refresh_lang: Unable to load translation for %s",
                              locale, exc_info=True)
            gettext.install("D-RATS")
            _ = gettext.gettext
        # pylint: disable=too-general-exception
        except Exception as error:
            self.logger.error("_refresh_lang: other error: %s", error)

        ##check if gettext works
        #try:
        #    self.logger.info("_refresh_lang: gettext: Check Hello world translation:  %s",
        #        (_("HELLO_WORLD")))
        # pylint: disable=too-general-exception
        # except Exception as error:
        #    self.logger.error("_refresh_lang: other error: %s", error)


    def _load_map_overlays(self):
        '''Load Map Overlays.'''
        self.stations_overlay = None

        self.map.clear_map_sources()

        source_types = [map_sources.MapFileSource,
                        map_sources.MapUSGSRiverSource,
                        map_sources.MapNBDCBuoySource]

        for stype in source_types:
            try:
                sources = stype.enumerate(self.config)
            except (NoOptionError, ValueError, OSError, TypeError):
                self.logger.info(
                    "_load_map_overlays: Failed to load source type %s",
                    stype, exc_info=True)
                continue

            for sname in sources:
                try:
                    source = stype.open_source_by_name(self.config, sname)
                    self.map.add_map_source(source)
                except (NoOptionError, OSError,
                        map_sources.MapSourceFailedToConnect):
                    self.logger.info(
                        "_load_map_overlays: Failed to load map source %s",
                        source.get_name(), exc_info=True)
                if sname == _("Stations"):
                    self.stations_overlay = source

        if not self.stations_overlay:
            fname = os.path.join(self.config.platform.config_dir(),
                                 "static_locations",
                                 _("Stations") + ".csv")
            try:
                # python 3 can be set to not raise this error
                os.makedirs(os.path.dirname(fname))
            except OSError as err:
                if err.errno != 17:  # File or directory exists
                    raise
            open(fname, "w").close()
            self.stations_overlay = map_sources.MapFileSource(_("Stations"),
                                                              "Static Overlay",
                                                              fname)

    def refresh_config(self):
        '''Refresh config.'''
        self.logger.info("Refreshing config...")

        _call = self.config.get("user", "callsign")
        gps.set_units(self.config.get("user", "units"))

        self._refresh_comms()
        self._refresh_gps()
        self._refresh_mail_threads()
        self._refresh_map()

        # The following line is needed to force language after config load
        # (not having this, the language is reverted back to untranslated labels
        # also if at D-Rats startup it was load (l))
        self._refresh_lang()

    def _refresh_map(self):
        '''
        Refresh Map.

        :returns: True
        :rtype: bool
        '''
        self.logger.info("_refresh_map: reconfigure Mapwindow with new map")

        # setup of the url for retrieving the map tiles depending
        # on the preference
        maptype = self.config.get("settings", "maptype")
        if maptype == "cycle":
            mapurl = self.config.get("settings", "mapurlcycle")
            mapkey = self.config.get("settings", "keyformapurlcycle")
        elif maptype == "landscape":
            mapurl = self.config.get("settings", "mapurllandscape")
            mapkey = self.config.get("settings", "keyformapurllandscape")
        elif maptype == "outdoors":
            mapurl = self.config.get("settings", "mapurloutdoors")
            mapkey = self.config.get("settings", "keyformapurloutdoors")
        else:
            mapurl = self.config.get("settings", "mapurlbase")
            mapkey = None
        # pylint: disable=fixme
        # todo: A change here should trigger a refresh of the new
        # map window after that a config reload/change is done
        # pylint: disable=broad-except
        self.logger.info("_refresh_map: reconfigured mapurl to: %s", mapurl)
        self.logger.info("_refresh_map: reconfigured mapkey to: %s", mapkey)
        Map.Window.set_base_dir(os.path.join(
            self.config.get("settings", "mapdir"), maptype), mapurl, mapkey)

        Map.Window.set_connected(
            self.config.getboolean("state", "connected_inet"))
        Map.Window.set_tile_lifetime(
            self.config.getint("settings", "map_tile_ttl") * 3600)
        proxy = self.config.get("settings", "http_proxy") or None
        Map.Window.set_proxy(proxy)

        self.map.set_title(
            "D-RATS Map Window - map in use: %s" %
            self.config.get("settings", "maptype"))
        self.map.set_zoom(14)
        self.map.queue_draw()
        return True

    def _refresh_location(self):
        '''
        Refresh Position Handler

        :returns: True to continue be triggered by the timer.
        :rtype: bool
        '''
        fix = self.get_position()

        if not self.__map_point:
            self.__map_point = map_sources.MapStation(fix.station,
                                                      fix.latitude,
                                                      fix.longitude,
                                                      fix.altitude,
                                                      fix.comment)
        else:
            self.__map_point.set_latitude(fix.latitude)
            self.__map_point.set_longitude(fix.longitude)
            self.__map_point.set_altitude(fix.altitude)
            self.__map_point.set_comment(fix.comment)
            self.__map_point.set_name(fix.station)

        comment = ''
        try:
            comment = self.config.get("settings", "default_gps_comment")
            if comment != self.default_comment:
                dprs_info = APRSicons.parse_dprs_message(text=comment)
                dprs_code = dprs_info['code']
                if 'overlay' in dprs_info:
                    dprs_code = dprs_info['code'] + dprs_info['overlay']
                fix.aprs_code = AprsDprsCodes.dprs_to_aprs(
                    code=dprs_code)
                self.default_comment = comment
        except (NoOptionError, DPRSInvalidCode):
            # silently fix this up.  Notifications here at info level will
            # flood the console log.
            self.logger.debug("_refresh_location comment='%s'",
                              comment, exc_info=True)
            fix.aprs_code = AprsDprsCodes.APRS_INFO_KIOSK_CODE
        if comment != self.default_comment:
            self.__map_point.set_pixbuf_from_aprs_code(code=fix.aprs_code)

            self.stations_overlay.add_point(self.__map_point)
            self.map.update_gps_status(self.gps.status_string())

        return True

    # pylint wants a max of 5 arguments
    # pylint: disable=too-many-arguments
    def __chat(self, src, dst, data, incoming, port):
        '''
        Chat internal.

        Here we manage the chat messages both incoming and outgoing

        :param src: Source
        :type src: str
        :param dst: Destination
        :type dst: str
        :param data: Chat data
        :type data: str
        :param incoming: True if message is incoming
        :type incoming: bool
        :param port: Radio port
        :type port: str
        '''
        if self.plugsrv:
            self.plugsrv.incoming_chat_message(src, dst, data)

        if src != "CQCQCQ":
            self.seen_callsigns.set_call_time(src, time.time())

        kwargs = {}

        if dst != "CQCQCQ":
            # so we are messaging into a private channel
            msg_to = " -> %s:" % dst
            kwargs["priv_src"] = src
        else:
            msg_to = ":"

        if src == "CQCQCQ":
            color = "brokencolor"
        elif incoming:
            color = "incomingcolor"
        else:
            color = "outgoingcolor"

        if port:
            portstr = "[%s] " % port
        else:
            portstr = ""

        line = "%s%s%s %s" % (portstr, src, msg_to, data)

        def do_incoming():
            self.mainwindow.tabs["chat"].display_line(line, incoming, color,
                                                      **kwargs)
        GLib.idle_add(do_incoming)

# ---------- STANDARD SIGNAL HANDLERS --------------------

    def __status(self, _obj, status):
        '''
        Status Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`base.Session`
        :type _obj: :class:`ui.main_messages.EventTab`
        :type _obj: :class:`ui.main_messages.FilesTab`
        :param status: Status
        :type status: str
        '''
        self.mainwindow.set_status(status)

    def __user_stop_session(self, _obj, sid, port, force=False):
        '''
        User Stop Session Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`ui.main_messages.EventTab`
        :param sid: Session ID
        :param sid: int
        :param port: Radio port
        :type port: str
        :param force: True to force session stop
        :type force: bool
        '''
        self.logger.info("User did stop session %i (force=%s)", sid, force)
        try:
            smgr, _sc = self.active_sessions[port]
            session = smgr.sessions[sid]
            session.close(force)
        except KeyError as err:
            self.logger.info("__user_stop_session: Session `%i' not found: %s",
                             sid, err)
            raise

    def __user_cancel_session(self, obj, sid, port):
        '''
        User Cancel Session.

        :param obj: Object signaled
        :type obj: :class:`ui.main_messages.EventTab`
        :param sid: Session ID
        :type sid: int
        :param port: Radio port
        :type port: str
        '''
        self.__user_stop_session(obj, sid, port, True)

    # pylint wants a max of 5 arguments
    # pylint: disable=too-many-arguments
    def __user_send_form(self, _obj, station, port, fname, sname):
        '''
        User Send Form.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`ui.main_messages.MessagesTab`
        :type _obj: :class:`msgrouting.MessageRouter`
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        :type _obj: :class:`emailgw.PeriodicAccountMailThread`
        :param station: Station to send form to
        :type station: str
        :param port: Radio port to send to
        :type port: str
        :param fname: Filename of form to send
        :type fname: str
        :param sname: Session name for sending
        :type sname: str
        '''
        self.session_coordinator(port).send_form(station, fname, sname)

    # pylint wants a max of 5 arguments
    # pylint: disable=too-many-arguments
    def __user_send_file(self, _obj, station, port, fname, sname):
        '''
        User Send File Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`ui.main_messages.EventTab`
        :type _obj: :class:`ui.main_messages.FilesTab`
        :type _obj: :class:`ui.main_stations.StationsList`
        :type _obj: :class:`pluginsrv.DRatsPluginProxy`
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        :param station: Station
        :type station: str
        :param port: Radio Port
        :type port: str
        :param fname: Filename
        :type fname: str
        :param sname: Session Name
        :type sname: str
        '''
        self.session_coordinator(port).send_file(station, fname, sname)

    # pylint wants a max of 5 arguments
    # pylint: disable=too-many-arguments
    def __user_send_chat(self, _obj, station, port, msg, raw):
        '''
        User send Chat Handler.

        This event is generated by pluginsrv/send_chat function while
        listening from the arriving messages.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`mainwindow.MainWindow`
        :type _obj: :class:`ui.main_chat.ChatTab`
        :type _obj: :class:`pluginsrv.DRatsPluginProxy`
        :type _obj: :class:`map.mapwindow.MapWindow`
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        :type _obj: :class:`emailgw.PeriodicAccountMailThread`
        :param station: Station
        :type station: :class:`str`
        :param port: Radio port
        :type port: :class:`str`
        :param msg: Chat message
        :type msg: :class:`str`
        :param raw: True if raw mode
        :type raw: bool
        '''
        if raw:
            self.chat_session(port).write_raw(msg)
        else:
            self.chat_session(port).write(msg, station)

    # pylint wants a max of 5 arguments
    # pylint: disable=too-many-arguments
    def __incoming_chat_message(self, _obj, src, dst, data, port=None):
        '''
        Incoming Chat Message Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`ui.main_stations.StationsList`
        :type _obj: :class:`sessions.chat.ChatSession`
        :param src: Source
        :type src: str
        :param dst: Destination
        :type dst: str
        :param data: Chat message data
        :type data: str
        :param port: Radio port, Default None
        :type port: str
        '''
        if dst not in ["CQCQCQ", self.config.get("user", "callsign")]:
            # This is not destined for us
            return
        self.__chat(src, dst, data, True, port)

    # pylint wants a max of 5 arguments
    # pylint: disable=too-many-arguments
    def __outgoing_chat_message(self, _obj, src, dst, data, port=None):
        '''
        Outgoing Chat Message Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`sessions.chat.ChatSession`
        :param src: Source
        :type src: str
        :param dst: Destination
        :type dst: str
        :param data: Chat data
        :type data: str
        :param port: Radio port
        :type port: str
        '''
        self.__chat(src, dst, data, False, port)

    def __get_station_list(self, _obj):
        '''
        Get Station List Handler.

        Used to get a dict of currently known stations indexed
        by the radio port the station was associated with.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`mainwindow.MainWindow`
        :type _obj: :class:`ui.main_messages.MessagesTab`
        :type _obj: :class:`ui.main_messages.FilesTab`
        :type _obj: :class:`ui.main_stations.StationsList`
        :type _obj: :class:`pluginsrv.DRatsPluginProxy`
        :type _obj: :class:`msgrouting.MessageRouter`
        :type _obj: :class:`map.mapwindow.MapWindow`
        :type _obj: :class:`emailgw.PeriodicAccountMailThread`
        :returns: station objects
        :rtype: dict
        '''
        stations = {}
        for port, (_sm, _sc) in self.active_sessions.items():
            stations[port] = []

        station_list = self.mainwindow.tabs["stations"].get_stations()

        for station in station_list:
            if station.get_port() not in list(stations.keys()):
                self.logger.info("__get_station_list: Station %s "
                                 "has unknown port %s",
                                 station, station.get_port())
            else:
                stations[station.get_port()].append(station)
        return stations

    def __get_message_list(self, _obj, station):
        '''
        Get Message List.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        :param station: Station
        :type station: str
        :returns: list of message tuple of title, stamp, filename for
                  the destination
        :rtype: list[tuple[str, int, str]]
        '''
        return self.mainwindow.tabs["messages"].get_shared_messages(station)

    def __submit_rpc_job(self, _obj, job, port):
        '''
        Submit RPC Job Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`ui.main_messages.FilesTab`
        :type _obj: :class:`ui.main_stations.StationsList`
        :type _obj: :class:`pluginsrv.DRatsPluginProxy`
        :param job: job
        :type job: :class:`sessions.RPCJob`
        :param port: Radio Port
        :type port: str
        '''
        self.rpc_session(port).submit(job)

    def __event(self, _obj, event):
        '''
        Event Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`ui.main_chat.ChatTab`
        :type _obj: :class:`ui.main_messages.MessagesTab`
        :type _obj: :class:`ui.main_messages.EventTab`
        :type _obj: :class:`ui.main_messages.FilesTab`
        :type _obj: :class:`ui.main_stations.StationsList`
        :type _obj: :class:`msgrouting.MessageRouter`
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        :type _obj: :class:`emailgw.PeriodicAccountMailThread`
        :param event: Event to log.
        :type event: :class:`main_events.Event`
        '''
        self.mainwindow.tabs["event"].event(event)

    def __config_changed(self, _obj):
        '''
        Config Changed Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`mainwindow.MainWindow`
        '''
        self.refresh_config()

    def __show_map_station(self, _obj, _station):
        '''
        Show Map of Station Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`mainwindow.MainWindow`
        :param _station: Station Unused
        :type _station: str
        '''
        self.logger.info("Showing Map Window")
        self.map.show()

    def __ping_station(self, _obj, station, port):
        '''
        Ping Station Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`mainwindow.MainWindow`
        :type _obj: :class:`ui.main_stations.StationsList`
        :type _obj: :class:`msgrouting.MessageRouter`
        :param station: Station
        :type station: str
        :param port: Radio port
        :type port: str
        '''
        self.chat_session(port).ping_station(station)

    def __ping_station_echo(self, _obj, station, port,
                            data, callback, cb_data):
        '''
        Ping Station Echo Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`ui.main_stations.StationsList`
        :param station: Remote station
        :type station: str
        :param port: Radio Port
        :type port: str
        :param data: Ping data
        :type data: str
        :param callback: Callback function
        :type callback: function
        :param cb_data: Callback data
        :type cb_data: str
        '''
        self.chat_session(port).ping_echo_station(station, data,
                                                  callback, cb_data)

    def __ping_request(self, _obj, src, dst, data, port):
        '''
        Ping Request Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`sessions.chat.ChatSession`
        :param src: Source
        :type src: str
        :param dst: Destination
        :type dst: str
        :param data: Ping data
        :type data: str
        :param port: Radio Port
        :type port: str
        '''
        msg = "%s pinged %s [%s]" % (src, dst, port)
        if data:
            msg += " (%s)" % data

        event = main_events.PingEvent(None, msg)
        self.mainwindow.tabs["event"].event(event)

    def __ping_response(self, _obj, src, dst, data, port):
        '''
        Ping Response Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`sessions.chat.ChatSession`
        :param src: Source
        :type src: str
        :param dst: Destination
        :type dst: str
        :param data: Ping data
        :type data: str
        :param port: Radio port
        :type port: str
        '''
        msg = "%s replied to ping from %s with: %s [%s]" % (src, dst,
                                                            data, port)
        event = main_events.PingEvent(None, msg)
        self.mainwindow.tabs["event"].event(event)

    def __incoming_gps_fix(self, _obj, fix, port):
        '''
        Incoming GPS Fix Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`sessions.chat.ChatSession`
        :param fix: GPS fix information
        :type fix: :class:`gps.GPSPosition`
        :param port: Radio Port
        :type port: str
        :return: Map source
        :rtype: :class:`StaticGPSSource`
        '''
        # Note, nothing seems to be using the return value.
        tstation = self.mainwindow.tabs["event"].last_event_time(fix.station)
        if (time.time() - tstation) > 300:
            self.mainwindow.tabs["event"].finalize_last(fix.station)

        fix.set_relative_to_current(self.get_position())
        event = main_events.PosReportEvent(fix.station, str(fix))
        self.mainwindow.tabs["event"].event(event)

        self.mainwindow.tabs["stations"].saw_station(fix.station, port)

        def source_for_station(station):
            maps = self.map.get_map_source(station)
            if maps:
                return maps

            try:
                self.logger.info(
                    "__incoming_gps_fix:  Creating a map source for %s",
                    station)
                maps = map_sources.MapFileSource.open_source_by_name(
                    self.config, station, True)
            except (NoOptionError, OSError,
                    map_sources.MapSourceFailedToConnect):
                # Unable to create or add so use "Stations" overlay
                return self.stations_overlay

            self.map.add_map_source(maps)

            return maps

        if self.config.getboolean("settings", "timestamp_positions"):
            source = source_for_station(fix.station)
            fix.station = "%s.%s" % (fix.station,
                                     time.strftime("%Y%m%d%H%M%S"))
        else:
            source = self.stations_overlay

        point = map_sources.MapStation(fix.station,
                                       fix.latitude,
                                       fix.longitude,
                                       fix.altitude,
                                       fix.comment)
        if fix.aprs_code is None:
            point.set_pixbuf_from_aprs_code(
                code=AprsDprsCodes.APRS_INFO_KIOSK_CODE)
            self.logger.info(
                "__incoming_gps_fix: aprs_code missing - forced to: %s ",
                AprsDprsCodes.APRS_INFO_KIOSK_CODE)
        else:
            point.set_pixbuf_from_aprs_code(code=fix.aprs_code)

        source.add_point(point)
        source.save()

        try:
            # load static data from configuration
            mapserver_active = self.config.get("settings", "mapserver_active")

        except NoOptionError:
            self.logger.info(
                "__incoming_gps_fix: Invalid static position: broad-except",
                exc_info=True, stack_info=True)

        # Send captured position to the mapserver to update our position sweeper
        if mapserver_active == "True":
            self.logger.info("__incoming_gps_fix:"
                             " Export to external mapserver active: %s"
                             " -- sending gps fix",
                             mapserver_active)
            # self.callback_gps(lat, lon, call, "altitude: "+alt)
            self.callback_gps(fix.latitude, fix.longitude, station=fix.station,
                              comments="altitude: " + str(fix.altitude))
        else:
            self.logger.info(
                "__incoming_gps_fix:"
                " Export to external mapserver not active: %s",
                mapserver_active)
        return gps.StaticGPSSource(fix.latitude, fix.longitude,
                                   fix.altitude, fix.station)

    def __station_status(self, _obj, sta, stat, msg, port):
        '''
        Station Status Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`sessions.chat.ChatSession`
        :param sta: Station
        :type sta: str
        :param stat: Status
        :type stat: str
        :param port: Radio Port
        :type port: str
        '''
        self.mainwindow.tabs["stations"].saw_station(sta, port, stat, msg)
        try:
            status = station_status.get_status_msgs()[stat]
        except KeyError:
            self.logger.info("Invalid station_status of %d.", stat)
            status = "code %d" % stat

        event = main_events.Event(None,
                                  "%s %s %s %s: %s" % (_("Station"),
                                                       sta,
                                                       _("is now"),
                                                       status,
                                                       msg))
        self.mainwindow.tabs["event"].event(event)

    def __get_current_status(self, _obj, _port):
        '''
        Get Current Status Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`sessions.chat.ChatSession`
        :port _port: Radio Port, Unused
        :type _port: str
        :returns: status
        :rtype: str
        '''
        return self.mainwindow.tabs["stations"].get_status()

    def __get_current_position(self, _obj, station):
        '''
        Get current position.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        :param station: Station to get position of
        :type station: str
        :raises: :class:`MainappStationNotFound`: if the station is not found
        :returns: GPS Position
        :rtype: :class:`GPSPosition`
        '''
        if station is None:
            return self.get_position()
        sources = self.map.get_map_sources()
        for source in sources:
            if source.get_name() == _("stations"):
                for point in source.get_points():
                    if point.get_name() == station:
                        fix = gps.GPSPosition(point.get_latitude(),
                                              point.get_longitude())
                        return fix
                break
        raise MainappStationNotFound("Station not found")

    def __session_started(self, _obj, id_num, msg, port):
        '''
        Session Started Internal.

        Don't register Chat, RPC, Sniff.

        :param _obj: Unused
        :param id_num: Session identification number
        :type id_num: int
        :param msg: Message
        :type msg: str
        :param port: Radio Port
        :type port: str
        :returns: event widget
        :rtype: :class:`SessionEvent`
        '''
        if id_num and id_num <= 3:
            return None
        if id_num == 0:
            msg = "Port connected"

        self.logger.info("Session Started In: [SESSION %i]: %s", id_num, msg)

        event = main_events.SessionEvent(id_num, port, msg)
        self.mainwindow.tabs["event"].event(event)
        return event

    def __session_status_update(self, obj, id_num, msg, port):
        '''
        Session Status Update.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`session_coordinator.SessionCoordinator`
        :param id_num: Session identification number
        :type id_num: int
        :param msg: Message
        :type msg: str
        :param port: Radio Port
        :type port: str
        '''
        self.__session_started(obj, id_num, msg, port)

    def __session_ended(self, obj, id_num, msg, restart_info, port):
        '''
        Session Ended.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`session_coordinator.SessionCoordinator`
        :param id_num: Session identification number
        :type id_num: int
        :param msg: Message
        :type msg: str
        :param restart_info: Restart information tuple of callsign, filename
        :type restart_info: tuple[str, str]
        :param port: Radio port, default=None
        :type port: str
        '''
        # Don't register Control, Chat, RPC, Sniff
        if id_num <= 4:
            return

        event = self.__session_started(obj, id_num, msg, port)
        event.set_restart_info(restart_info)
        event.set_as_final()

        fname = None
        if restart_info:
            fname = restart_info[1]

        self.msgrouter.form_xfer_done(fname, port, True)

    # pylint wants a max of 15 local variables
    # pylint: disable=too-many-locals
    def __form_received(self, _obj, id_num, fname, port=None):
        '''
        Form Received Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`msgrouting.MessageRouter`
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        :type _obj: :class:`session_coordinator.SessionCoordinator`
        :type _obj: :class:`emailgw.PeriodicAccountMailThread`
        :param id_num: Session identification number
        :type id_num: int
        :param fname: Form name
        :type fname: str
        :param port: Radio port, default None
        :type port: str
        '''
        if port:
            id_str = "%s_%s" % (id_num, port)
        else:
            id_str = str(id_num)

        self.logger.info("__form_received: [NEWFORM %s]: %s", id_str, fname)
        ffile = formgui.FormFile(fname)

        msg = '%s "%s" %s %s' % (_("Message"),
                                 ffile.get_subject_string(),
                                 _("received from"),
                                 ffile.get_sender_string())

        myc = self.config.get("user", "callsign")
        dst = ffile.get_path_dst()
        src = ffile.get_path_src()
        pth = ffile.get_path()

        fwd_on = self.config.getboolean("settings", "msg_forward")
        is_dst = msgrouting.is_sendable_dest(myc, dst)
        nextst = msgrouting.gratuitous_next_hop(dst, pth) or dst
        bounce = "@" in src and "@" in dst
        isseen = myc in ffile.get_path()[:-1]

        self.logger.info("__form_received: Decision: "
                         "fwd:%s "
                         "sendable:%s "
                         "next:%s "
                         "bounce:%s "
                         "seen:%s ",
                         fwd_on, is_dst, nextst, bounce, isseen)

        if fwd_on and is_dst and not bounce and not isseen:
            msg += " (%s %s)" % (_("forwarding to"), nextst)
            msgrouting.move_to_outgoing(self.config, fname)
            refresh_folder = "Outbox"
        else:
            refresh_folder = "Inbox"

        if msgrouting.msg_is_locked(fname):
            msgrouting.msg_unlock(fname)
        self.mainwindow.tabs["messages"].refresh_if_folder(refresh_folder)

        event = main_events.FormEvent(id_str, msg)
        event.set_as_final()
        self.mainwindow.tabs["event"].event(event)

    def __file_received(self, _obj, id_num, fname, port=None):
        '''
        File Received.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`session_coordinator.SessionCoordinator`
        :param id_num: Session identification number
        :type id_num: int
        :param fname: File name
        :type fname: str
        :param port: Radio port, default None
        :type port: str
        '''
        if port:
            id_str = "%s_%s" % (id_num, port)
        else:
            id_str = str(id_num)
        _fn = os.path.basename(fname)
        msg = '%s "%s" %s' % (_("File"), _fn, _("Received"))
        event = main_events.FileEvent(id_str, msg)
        event.set_as_final()
        self.mainwindow.tabs["files"].refresh_local()
        self.mainwindow.tabs["event"].event(event)

    def __form_sent(self, _obj, id_num, fname, port=None):
        '''
        Form Sent Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`msgrouting.MessageRouter`
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        :type _obj: :class:`session_coordinator.SessionCoordinator`
        :param id_num: id_num
        :type id_num: int
        :param fname: Form name
        :type fname: str
        :param port: Radio port, default None
        :type port: str
        '''
        self.msgrouter.form_xfer_done(fname, port, False)
        if port:
            id_str = "%s_%s" % (id_num, port)
        else:
            id_str = str(id_num)
        self.logger.info("[FORMSENT %s]: %s", id_str, fname)
        event = main_events.FormEvent(id, _("Message Sent"))
        event.set_as_final()

        self.mainwindow.tabs["messages"].message_sent(fname)
        self.mainwindow.tabs["event"].event(event)

    def __file_sent(self, _obj, id_num, fname, port=None):
        '''
        File sent.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`session_coordinator.SessionCoordinator`
        :param id_num: Session identification number
        :type id_num: str
        :param fname: File name
        :type fname: str
        :param port: Radio port, default None
        :type port: str
        '''
        if port:
            id_str = "%s_%s" % (id_num, port)
        else:
            id_str = str(id_num)
        self.logger.info("[FILESENT %s]: %s", id_str, fname)
        base_fname = os.path.basename(fname)
        msg = '%s "%s" %s' % (_("File"), base_fname, _("Sent"))
        event = main_events.FileEvent(id_str, msg)
        event.set_as_final()
        self.mainwindow.tabs["files"].file_sent(fname)
        self.mainwindow.tabs["event"].event(event)

    def __get_chat_port(self, _obj):
        '''
        Get Chat Port Handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`mainwindow.MainWindow`
        :returns: port used for chat
        :rtype: str
        '''
        return self.mainwindow.tabs["chat"].get_selected_port()

    def __trigger_msg_router(self, _obj, account):
        '''
        Trigger message router handler.

        :param _obj: Object signaled, Unused
        :type _obj: :class:`ui.main_messages.MessagesTab`
        :param account: Email account
        :type account: str
        '''
        if not account:
            self.msgrouter.trigger()
        elif account == "@WL2K":
            call = self.config.get("user", "callsign")
            mthread = wl2k.wl2k_auto_thread(self, call)
            self.__connect_object(mthread)
            mthread.start()
        elif account in list(self.mail_threads.keys()):
            self.mail_threads[account].trigger()
        else:
            mthread = AccountMailThread(self.config, account)
            mthread.start()

    def __register_object(self, _parent, obj):
        '''
        Register Object Handler.

        :param _parent: Object signaled, Unused
        :type _parent: :class:`sessions.rpc.RPCActionSet`
        :param _obj: Object to connect to handler
        :type _obj: :class:`GObject.GObject`
        :type _obj: :class:`sessions.rpc.RPCActionSet`
        '''
        self.__connect_object(obj)

# ------------ END SIGNAL HANDLERS ----------------

    def __connect_object(self, obj, *args):
        '''
        Connect Object to handler.

        :param obj: object to connect
        :param `*args`: Variable arguments
        '''
        # pylint: disable=protected-access
        for signal in obj._signals.keys():
            handler = self.handlers.get(signal, None)
            if handler is None:
                pass
            # raise Exception("Object signal `%s' of object %s not known" % \
            #                        (signal, obj))
            elif self.handlers[signal]:
                try:
                    obj.connect(signal, handler, *args)
                except TypeError as err:
                    self.logger.info(
                        "__connect_object: Failed to attach signal %s :%s",
                        signal, err)
                    raise

    def _announce_self(self):
        '''Announce self.'''
        self.logger.info("D-RATS v%s starting at %s on %s",
                         version.DRATS_VERSION,
                         time.asctime(),
                         Platform.get_platform())

    def get_position(self):
        '''
        Get position.

        :returns: Position
        :rtype: :class:`GPSPosition`
        '''
        pos = self.gps.get_position()
        pos.set_station(self.config.get("user", "callsign"))
        try:
            pos.set_station(self.config.get("user", "callsign"),
                            self.config.get("settings", "default_gps_comment"))
        except (NoOptionError, gps.GpsDprsChecksumError):
            pass
        return pos

    def load_static_routes(self):
        '''Load static routes.'''
        routes = self.config.platform.config_file("routes.txt")
        if not os.path.exists(routes):
            return

        froutes = open(routes)
        lines = froutes.readlines()
        lno = 0
        for line in lines:
            lno += 1
            if not line.strip() or line.startswith("#"):
                continue

            try:
                _routeto, station, port = line.split()
            except ValueError:
                self.logger.info(
                    "load_static_routes: Line %i of %s not valid",
                    lno, routes)
                continue

            self.mainwindow.tabs["stations"].saw_station(station.upper(), port)
            if port in self.active_sessions:
                smgr, _sc = self.active_sessions[port]
                smgr.manual_heard_station(station)

    def clear_all_msg_locks(self):
        '''Clear all message locks.'''
        path = os.path.join(self.config.platform.config_dir(),
                            "messages",
                            "*",
                            ".lock*")
        for lock in glob.glob(path):
            self.logger.info("Removing stale message lock %s", lock)
            os.remove(lock)

    # pylint wants wants a maximum of 15 local variables
    # pylint wants a maximum of 12 branches
    # pylint wants a maximum of 50 statements
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def main(self):
        '''Main.'''
        # Copy default forms before we start
        distdir = Platform.get_platform().sys_data()
        userdir = self.config.form_source_dir()
        dist_forms = glob.glob(os.path.join(distdir, "forms", "*.x?l"))
        for form in dist_forms:
            fname = os.path.basename(form)
            user_fname = os.path.join(userdir, fname)

            try:
                needupd = \
                    (os.path.getmtime(form) > os.path.getmtime(user_fname))
            except FileNotFoundError:
                needupd = True
            if not os.path.exists(user_fname) or needupd:
                self.logger.info("Installing dist form %s -> %s",
                                 fname, user_fname)
                try:
                    shutil.copyfile(form, user_fname)
                except (OSError, shutil.SameFileError) as err:
                    self.logger.info("Copyfile FAILED: %s", err)
                    raise

        self.clear_all_msg_locks()

        if self.config.options("ports") and \
                self.config.has_option("settings", "port"):
            self.logger.info("Migrating single-port config to multi-port")

            port = self.config.get("settings", "port")
            rate = self.config.get("settings", "rate")
            snif = self.config.getboolean("settings", "sniff_packets")
            comp = self.config.getboolean("settings", "compatmode")

            self.config.set("ports",
                            "port_0",
                            "%s,%s,%s,%s,%s,%s" % (True,
                                                   port,
                                                   rate,
                                                   snif,
                                                   comp,
                                                   "DEFAULT"))
            for i in ["port", "rate", "sniff_packets", "compatmode"]:
                self.config.remove_option("settings", i)

        # LOAD THE MAIN WINDOW
        self.logger.info("load the main window")
        # pylint: disable=broad-except
        try:
            self.run(None)
        except KeyboardInterrupt:
            pass
        except Exception:
            self.logger.info("Got broad-exception on close", exc_info=True)
            # broad/bare exceptions make debugging harder
            raise

        self.logger.info("Saving config...")
        self.config.save()

        if self.config.getboolean("prefs", "dosignoff") and \
                self.active_sessions:
            msg = self.config.get("prefs", "signoff")
            status = station_status.STATUS_OFFLINE
            for port in self.active_sessions:
                port_session = self.chat_session(port)
                if port_session:
                    port_session.advertise_status(status, msg)
                else:
                    self.logger.info("main: python3 crashed here.")

            time.sleep(2) # HACK


def get_mainapp():
    '''
    Get mainapp.

    :returns: MAINAPP
    :rtype: :class:`MainApp`
    '''
    return MAINAPP
