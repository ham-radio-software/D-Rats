#
'''Message Routing'''
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

from __future__ import absolute_import
from __future__ import print_function

import logging
import threading
import time
import os
import smtplib
import shutil
import traceback
from glob import glob

from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib
from gi.repository import GObject

from . import formgui
from . import signals

from . import utils
from . import wl2k


class MsgRoutingException(Exception):
    '''Generic MsgRouting Exception.'''


class MessageRouterException(MsgRoutingException):
    '''Generic Message Router Exception.'''


class EmailTypeRequired(MessageRouterException):
    '''Email message type required.'''


CALL_TIMEOUT_RETRY = 300

MSG_LOCK_LOCK = threading.Lock()

MSGROUTING_LOGGER = logging.getLogger("MsgRouting")


def __msg_lockfile(fname):
    name = os.path.basename(fname)
    path = os.path.dirname(fname)
    return os.path.join(path, ".lock.%s" % name)


def msg_is_locked(fname):
    '''
    Message is locked?

    :param fname: Lock filename
    :type fname: str
    :returns: True if the lock filename exists
    :rtype: bool
    '''
    return os.path.exists(__msg_lockfile(fname))


def msg_lock(fname):
    '''
    Message Lock

    :param fname: Filename for lock
    :type fname: str
    :returns: True if lock is successful
    :rtype: bool
    '''
    MSG_LOCK_LOCK.acquire()
    if not msg_is_locked(fname):
        lock = open(__msg_lockfile(fname), "w")
        traceback.print_stack(file=lock)
        lock.close()
        success = True
    else:
        lock = open(__msg_lockfile(fname), "r")
        MSGROUTING_LOGGER.info("msg_lock: "
                               "------ LOCK OWNED BY -------\n%s------------\n",
                               lock.read())
        lock.close()
        success = False
    MSG_LOCK_LOCK.release()

    # MSGROUTING_LOGGER.info("Locked %s: %s", fname, success)
    return success


def msg_unlock(fname):
    '''
    Message Unlock

    :param fname: Lock filename
    :type fname: str
    :returns: True if the unlock is successful
    :rtype: bool
    '''
    success = True
    MSG_LOCK_LOCK.acquire()
    try:
        os.remove(__msg_lockfile(fname))
    except OSError:
        utils.log_exception()
        success = False
    MSG_LOCK_LOCK.release()

    # MSGROUTING_LOGGER.info("Unlocked %s: %s", fn, success)
    return success


def gratuitous_next_hop(route, path):
    '''
    Gratuitous Next Hop

    :param route: Route information
    :type route: str
    :param path: Route for path
    :type path: str
    :returns: Route Nodes or None
    :rtype: str
    '''
    path_nodes = path[1:]
    route_nodes = route.split(";")

    if len(path_nodes) >= len(route_nodes):
        MSGROUTING_LOGGER.info("gratuitous_next_hop: "
                               "Nothing left in the routes")
        return None


    # pylint: disable=consider-using-enumerate
    for i in range(0, len(path_nodes)):
        if path_nodes[i] != route_nodes[i]:
            MSGROUTING_LOGGER.info("gratuitous_next_hop: Path element "
                                   "%i (%s) does not match route %s",
                                   i, path_nodes[i], route_nodes[i])
            return None

    return route_nodes[len(path_nodes)]


# pylint: disable=too-many-return-statements
def is_sendable_dest(mycall, string):
    '''
    Is sendable Dest?

    :param mycall: Callsign to check
    :type mycall: str
    :param string: string value
    :type string: str
    :returns: True if sendable
    :rtype: bool
    '''
    # Specifically for me
    if string == mycall:
        MSGROUTING_LOGGER.info("is_sendable_dest: msg for me")
        return False

    # Empty string
    if not string.strip():
        MSGROUTING_LOGGER.info("is_sendable_dest: empty: %s %s",
                               string, string.strip())
        return False

    # Is an email address:
    if "@" in string:
        MSGROUTING_LOGGER.info("is_sendable_dest: is an Email")
        return True

    # Contains lowercase characters
    if string != string.upper():
        MSGROUTING_LOGGER.info("is_sendable_dest: lowercase")
        return False

    # Contains spaces
    if string != string.split()[0]:
        MSGROUTING_LOGGER.info("is_sendable_dest: spaces")
        return False

    # Contains a gratuitous route and we're the last in line
    if ";" in string and string.split(";")[-1] == mycall:
        MSGROUTING_LOGGER.info("is_sendable_dest: End of gratuitous route")
        return False

    MSGROUTING_LOGGER.info("is_sendable_dest: default to call")

    # Looks like it's a candidate to be routed
    return True


def form_to_email(config, msgfn, replyto=None):
    '''
    Form to E-mail

    :param config: Config object
    :type config: :class:`DratsConfig`
    :param msgfn: Message file name
    :type msgfn: str
    :param replyto: Optional replyto destination
    :type replyto: str
    :returns: Email data
    :rtype: :class:`MIMEMultipart`
    '''
    form = formgui.FormFile(msgfn)
    form.configure(config)

    if not replyto:
        replyto = "DO_NOT_REPLY@d-rats.com"

    sender = form.get_path_src()
    for i in "<>\"'":
        if i in sender:
            sender = sender.replace(i, "")

    root = MIMEMultipart("related")
    root["Subject"] = form.get_subject_string()
    root["From"] = '"%s" <%s>' % (sender, replyto)
    root["To"] = form.get_path_dst()
    root["Reply-To"] = root["From"]
    root["Message-id"] = form.get_path_mid()
    root.preamble = "This is a multi-part message in MIME format"

    altp = MIMEMultipart("alternative")
    root.attach(altp)

    warn = "This message is a D-RATS rich form and is only viewable " +\
        "in D_RATS itself or in an HTML-capable email client"

    if form.ident == "email":
        altp.attach(MIMEText(form.get_field_value("message"), "plain"))
    else:
        altp.attach(MIMEText(warn, "plain"))
        altp.attach(MIMEText(form.export_to_string(), "html"))

    payload = MIMEBase("d-rats", "form_xml")
    payload.set_payload(form.get_xml())
    payload.add_header("Content-Disposition",
                       "attachment",
                       filename="do_not_open_me")
    root.attach(payload)
    del form
    return root


def move_to_folder(config, msg, folder):
    '''
    Move to folder

    :param config: Config object
    :type config: :class:`DratsConfig`
    :param msg: Message to move
    :type msg: str
    :param folder: Destination folder
    :type folder: str
    '''
    newfn = os.path.join(config.form_store_dir(),
                         folder,
                         os.path.basename(msg))
    msg_lock(newfn)
    shutil.move(msg, newfn)
    msg_unlock(newfn)


def move_to_outgoing(config, msg):
    '''
    Move to outgoing

    :param config: Config object
    :type config: :class:`DratsConfig`
    :param msg: Message to move
    :type msg: str
    :returns: Result of move to folder, which does not have a return value
    :rtype: none
    '''
    return move_to_folder(config, msg, "Outbox")


# pylint: disable=too-few-public-methods
class MessageRoute():
    '''
    Message Route.

    :param line: String containing a destination, gateway, and port
    :type line: str
    '''

    # This class does not appear to be used anywhere
    def __init__(self, line):
        self.dest, self.gateway, self.port = line.split()


# pylint: disable=too-many-instance-attributes
class MessageRouter(GObject.GObject):
    '''
    Message Router.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param mainapp: Main application
    :type mainapp: :class:`MainApp`
    :param validate_incoming: Incoming e-mail validation function
    :type validate_incoming: function
    '''

    __gsignals__ = {
        "get-station-list" : signals.GET_STATION_LIST,
        "user-send-form" : signals.USER_SEND_FORM,
        "form-sent" : signals.FORM_SENT,
        "form-received" : signals.FORM_RECEIVED,
        "ping-station" : signals.PING_STATION,
        "event" : signals.EVENT,
        }
    _signals = __gsignals__

    def __init__(self, config, mainapp, validate_incoming):
        GObject.GObject.__init__(self)
        self.logger = logging.getLogger("MessageRouter")

        self.__event = threading.Event()

        self.__config = config
        # Hack, need to refactor so that nothing
        # call routines in mainapp.
        # Common routines should be in their own module.
        self._mainapp = mainapp

        # Hack because message checking is part of this module instead
        # of being in its own module, causing a co-dependency of emailgw and
        # this module that should not exist.
        self._validate_incoming = validate_incoming

        self.__sent_call = {}
        self.__sent_port = {}
        self.__file_to_call = {}
        self.__failed_stations = {}
        self.__pinged_stations = {}

        self.__thread = None
        self.__enabled = False

    def _emit(self, signal, *args):
        GLib.idle_add(self.emit, signal, *args)

    def __proxy_emit(self, signal):
        def handler(_obj, *args):
            self.logger.info("Proxy emit %s: %s", signal, args)
            self._emit(signal, *args)
        return handler

    def _get_routes(self):
        '''
        Get Routes internal.

        :returns: Routes keyed by gateway
        :rtype: dict
        '''
        r_file = self.__config.platform.config_file("routes.txt")
        try:
            f_handle = open(r_file)
            lines = f_handle.readlines()
            f_handle.close()
        except IOError:
            return {}

        routes = {}

        for line in lines:
            if not line.strip() or line.startswith("#"):
                continue
            try:
                dest, gateway, _port = line.split()
                routes[dest] = gateway
            except ValueError as err:
                self.logger.info("_get_routes: Error parsing line '%s': %s",
                                 line, err)

        return routes

    def _sleep(self):
        t_limit = self.__config.getint("settings", "msg_flush")
        time.sleep(t_limit)

    def _get_queue(self):
        '''
        Get queue internal.

        :returns: files queued for each callsign
        :rtype: dict
        '''
        queue = {}

        q_dir = os.path.join(self.__config.form_store_dir(), "Outbox")
        filename_list = glob(os.path.join(q_dir, "*.xml"))
        for filename in filename_list:
            if not msg_lock(filename):
                self.logger.info("_get_queue: Message %s is locked, skipping",
                                 filename)
                continue

            form = formgui.FormFile(filename)
            call = form.get_path_dst()
            del form

            if not call:
                if msg_is_locked(filename):
                    msg_unlock(filename)
                continue
            if call not in queue:
                queue[call] = [filename]
            else:
                queue[call].append(filename)

        return queue

    def _send_form(self, call, port, filename):
        '''
        Send form.

        :param call: Call sign to send to
        :type call: str
        :param port: Radio port
        :type port: str
        :param filename: Filename for message
        :type filename: str
        '''
        self.__sent_call[call] = time.time()
        self.__sent_port[port] = time.time()
        self.__file_to_call[filename] = call
        self._emit("user-send-form", call, port, filename, "Foo")

    def _sent_recently(self, call):
        if call in self.__sent_call:
            return (time.time() - self.__sent_call[call]) < CALL_TIMEOUT_RETRY
        return False

    def _port_free(self, port):
        return port not in self.__sent_port

    # pylint: disable=too-many-arguments, too-many-branches, too-many-statements
    def _route_msg(self, src, dst, path, slist, routes):
        '''
        Route msg internal.

        :param src: Source address of message.
        :type call: str
        :param dst: Destination address of message.
        :type dst: str
        :param path: Path to route message
        :type path: str
        :param slist: List of active stations
        :type slist: dict
        :param routes: Routes for message
        :type routes: dict
        :returns: True
        :rtype bool
        '''
        invalid = []

        def old(call):
            station = slist.get(call, None)
            if not station:
                return True
            ttl = self.__config.getint("settings", "station_msg_ttl")
            return (time.time() - station.get_heard()) > ttl

        while True:
            # Choose the @route for @dst
            if ";" in dst:
                # Gratuitous routing takes precedence
                route = gratuitous_next_hop(dst, path)
                self.logger.info("_route_msg: Route for %s: %s (%s)",
                                 dst, route, path)
                break
            if "@" in dst and dst not in invalid and \
                    not ":" in dst and \
                    self._validate_incoming(self.__config, src, dst):
                # Out via email
                route = dst
            elif dst in slist and dst not in invalid:
                # Direct send
                route = dst
            elif dst in routes and routes[dst] not in invalid:
                # Static route present
                route = routes[dst]
            elif "*" in routes and routes["*"] not in invalid:
                # Default route
                route = routes["*"]
            elif dst.upper().startswith("WL2K:"):
                route = dst
            else:
                route = None
                break

            # Validate the @route

            if route.upper().startswith("WL2K:"):
                break # WL2K is easy
            if route != dst and route in path:
                self.logger.info("_route_msg: Route %s in path", route)
                invalid.append(route)
                route = None # Don't route to the same location twice
            elif self._is_station_failed(route):
                self.logger.info("_route_msg: Route %s is failed", route)
                invalid.append(route)
                route = None # This one is not responding lately
            elif old(route) and self._station_pinged_out(route):
                self.logger.info("_route_msg: Route %s for %s is pinged out",
                                 route, dst)
                invalid.append(route)
                route = None # This one has been pinged and isn't responding
            else:
                break # We have a route to try

        if not route:
            self.logger.info("_route_msg: No route for station %s", dst)
        elif old(route) and "@" not in route and ":" not in route:
            # This station is heard, but a long time ago.  Ping it first
            # and consider it unrouteable for now
            route_station = slist.get(route, None)
            self._station_pinged_incr(route)
            if route_station:
                self.logger.info("_route_msg: Pinging stale route %s", route)
                self._emit("ping-station", route, route_station.get_port())
            route = None
        else:
            self._station_pinged_clear(route)
            self.logger.info("_route_msg: Routing message for %s to %s",
                             dst, route)

        return route

    def _form_to_wl2k_em(self, dst, msgfn):
        form = formgui.FormFile(msgfn)

        if form.ident != "email":
            raise EmailTypeRequired("WL2K support requires email type message")

        payload = form.get_field_value("message")

        call = self.__config.get("user", "callsign")
        call = "".join([x for x in call if x.isalpha()])

        attachments = []
        for name, _length in form.get_attachments():
            data = form.get_attachment(name)
            attachments.append(wl2k.WinLinkAttachment(name, data))

        msg = wl2k.WinLinkMessage()
        msg.encode_message(form.get_path_src(),
                           [dst],
                           form.get_subject_string(),
                           payload,
                           attachments)

        return msg

    def _route_via_email(self, _call, msgfn):
        '''
        Route via email internal.

        :param _call: callsign unused.
        :type _call: str
        :param msgfn: Message filename
        :type msgfn: str
        :returns: True
        :rtype bool
        '''
        server = self.__config.get("settings", "smtp_server")
        replyto = self.__config.get("settings", "smtp_replyto")
        tls = self.__config.getboolean("settings", "smtp_tls")
        user = self.__config.get("settings", "smtp_username")
        pwrd = self.__config.get("settings", "smtp_password")
        port = self.__config.getint("settings", "smtp_port")

        msg = form_to_email(self.__config, msgfn, replyto)

        mailer = smtplib.SMTP(server, port)
        mailer.set_debuglevel(1)

        mailer.ehlo()
        if tls:
            mailer.starttls()
            mailer.ehlo()
        if user and pwrd:
            mailer.login(user, pwrd)

        mailer.sendmail(replyto, msg["To"], msg.as_string())
        mailer.quit()
        self._emit("form-sent", -1, msgfn)

        return True

    def _route_via_station(self, call, route, slist, msg):
        '''
        Route via station internal.

        :param call: callsign for station.
        :type call: str
        :param route: Route for message
        :type route: dict
        :param slist: List of active stations
        :type slist: dict
        :param msg: Message
        :type msg: str
        :returns: True
        :rtype bool
        '''
        if self._sent_recently(route):
            self.logger.info("_route_via_station: Call %s is busy", route)
            return False

        self.logger.info("_route_va_station: %s", slist)
        port = slist[route].get_port()
        if not self._port_free(port):
            self.logger.info("_route_via_station: I think port %s is busy",
                             port)
            return False # likely already a transfer going here so skip it

        self.logger.info("_route_via_station: Sending %s to %s (via %s)",
                         msg, call, route)
        self._send_form(route, port, msg)

        return True

    def _route_via_wl2k(self, src, dst, msgfn):
        '''
        Route via wl2k internal.

        :param src: source of message.
        :type src: str
        :param dst: Destination for message
        :type dst: str
        :param msgfn: Message Filename
        :type msgfn: str
        :returns: True
        :rtype bool
        '''
        # Temporary to get diagnostics about wl2k failures.
        self.logger.info('_route_via_station: '
                         'src %s %s dst %s %s msgfn %s %s',
                         type(src), src, type(dst), dst, type(msgfn), msgfn)
        _part, addr = dst.split(":")
        msg = self._form_to_wl2k_em(addr, msgfn)

        def complete(_thread, status, error):
            if status:
                self._emit("form-sent", -1, msgfn)
            else:
                self.logger.info("_route_vi_wl2k: Failed to send via WL2K: %s",
                                 error)

        msg_thread = wl2k.wl2k_auto_thread(self._mainapp,
                                           src, send_msgs=[msg])
        msg_thread.connect("mail-thread-complete", complete)
        msg_thread.connect("event", self.__proxy_emit("event"))
        msg_thread.connect("form-received", self.__proxy_emit("form-received"))
        msg_thread.connect("form-sent", self.__proxy_emit("form-sent"))
        msg_thread.start()

        return True

    def _route_message(self, msg, slist, routes):
        '''
        Route message internal.

        :param msg: message filename to send.
        :type msg: str
        :param slist: List of active stations
        :type slist: dict
        :param routes: Routes for message
        :type routes: dict
        :returns: True if a route found.
        :rtype bool
        '''
        form = formgui.FormFile(msg)
        path = form.get_path()
        emok = path[-2:] != ["EMAIL", self.__config.get("user", "callsign")]
        src = form.get_path_src()
        dst = form.get_path_dst()
        del form

        routed = False
        route = self._route_msg(src, dst, path, slist, routes)

        if not route:
            pass
        elif route.upper().startswith("WL2K:"):
            routed = self._route_via_wl2k(src, route, msg)
        elif "@" in src and "@" in dst:
            # Don't route a message from email to email
            pass
        elif "@" in route:
            if emok:
                routed = self._route_via_email(dst, msg)
        else:
            routed = self._route_via_station(dst, route, slist, msg)

        return routed

    def _run_one(self, queue):
        '''
        Run one internal.

        :param queue: Queue of outgoing messages
        :type queue: dict
        '''
        plist = self.emit("get-station-list")
        slist = {}

        routes = self._get_routes()

        if plist:
            for _port, stations in plist.copy().items():
                for station in stations:
                    slist[str(station)] = station
        else:
            self.logger.info("_run_one: Station list was empty")

        for _dst, callq in queue.copy().items():
            for msg in callq:

                try:
                    routed = self._route_message(msg, slist, routes)
                # pylint: disable=broad-except
                except Exception:
                    self.logger.info("_run_one: broad-except", exc_info=True)
                    utils.log_exception()
                    routed = False

                if not routed:
                    if msg_is_locked(msg):
                        self.logger.info("_run_one: unlocking message %s", msg)
                        msg_unlock(msg)

    def _run(self):
        while self.__enabled:
            if self.__config.getboolean("settings", "msg_forward") or \
                    self.__event.is_set():
                # self.logger.info("_run: Running routing loop")
                queue = self._get_queue()

                try:
                    self._run_one(queue)
                # pylint: disable=broad-except
                except Exception:
                    utils.log_exception()
                    self.logger.info("_run: Fail-safe unlocking messages "
                                     "in queue: broad-except", exc_info=True)
                    for msgs in queue.values():
                        for msg in msgs:
                            self.logger.info("_run: Unlocking %s", msg)
                            if msg_is_locked(msg):
                                msg_unlock(msg)

                self.__event.clear()
            self.__event.wait(self.__config.getint("settings", "msg_flush"))

    def trigger(self):
        '''Trigger.'''
        if not self.__thread.is_alive():
            self.start()
        else:
            self.__event.set()

    def start(self):
        '''Start.'''
        self.logger.info("_route_via_station: Starting message router thread")
        self.__enabled = True
        self.__event.clear()
        self.__thread = threading.Thread(target=self._run)
        self.__thread.daemon = True
        self.__thread.start()

    def stop(self):
        '''Stop.'''
        self.__enabled = False
        self.__thread.join()

    @staticmethod
    def _update_path(fname, call):
        form = formgui.FormFile(fname)
        form.add_path_element(call)
        form.save_to(fname)

    def _station_succeeded(self, call):
        self.__failed_stations[call] = 0

    def _station_failed(self, call):
        self.__failed_stations[call] = self.__failed_stations.get(call, 0) + 1
        self.logger.info("_station_failed: Fail count for %s is %i",
                         call, self.__failed_stations[call])

    def _is_station_failed(self, call):
        return self.__failed_stations.get(call, 0) >= 3

    def _station_pinged_incr(self, call):
        self.__pinged_stations[call] = self.__pinged_stations.get(call, 0) + 1
        return self.__pinged_stations[call]

    def _station_pinged_clear(self, call):
        self.__pinged_stations[call] = 0

    def _station_pinged_out(self, call):
        return self.__pinged_stations.get(call, 0) >= 3

    def form_xfer_done(self, fname, port, failed):
        '''
        Form Transfer Done.

        :param fname: Filename of form
        :type fname: str
        :param port: Port for transport
        :type port: str
        :param failed: True if the transfer failed
        :type failed: bool
        '''
        self.logger.info("form_xfer_done: File %s on %s done", fname, port)

        if fname and msg_is_locked(fname):
            msg_unlock(fname)

        call = self.__file_to_call.get(fname, None)
        if call and call in self.__sent_call:
            # This callsign completed (or failed) a transfer
            if failed:
                self._station_failed(call)
            else:
                self._station_succeeded(call)
                self._update_path(fname, call)

            del self.__sent_call[call]
            del self.__file_to_call[fname]

        if port in self.__sent_port:
            # This port is now open for another transfer
            del self.__sent_port[port]
