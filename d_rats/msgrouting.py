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

from __future__ import absolute_import
from __future__ import print_function
import sys
import threading
import time
import os
import smtplib
import shutil
from glob import glob
from six.moves import range

try:
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email.message import Message
except ImportError:
    # Python 2.4
    from email import MIMEMultipart
    from email import MIMEBase
    from email import MIMEText 
    from email import Message 

import gobject

from . import formgui
from . import signals
#py3   from . import emailgw


from . import utils
from . import wl2k

#py3   from . import mainapp


import traceback

CALL_TIMEOUT_RETRY = 300

MSG_LOCK_LOCK = threading.Lock()

def __msg_lockfile(fn):
    name = os.path.basename(fn)
    path = os.path.dirname(fn)
    return os.path.join(path, ".lock.%s" % name)

def msg_is_locked(fn):
    return os.path.exists(__msg_lockfile(fn))

def msg_lock(fn):
    MSG_LOCK_LOCK.acquire()
    if not msg_is_locked(fn):
        lf = open(__msg_lockfile(fn), "w")
        traceback.print_stack(file=lf)
        lf.close()
        success = True
    else:
        lf = open(__msg_lockfile(fn), "r")
        print(("Msgrouting: ------ LOCK OWNED BY -------\n%s------------\n" % lf.read()))
        lf.close()
        success = False
    MSG_LOCK_LOCK.release()

    #print("Locked %s: %s" % (fn, success))
    return success

def msg_unlock(fn):
    success = True
    MSG_LOCK_LOCK.acquire()
    try:
        os.remove(__msg_lockfile(fn))
    except OSError:
        utils.log_exception()
        success = False
    MSG_LOCK_LOCK.release()

    #print("Unlocked %s: %s" % (fn, success))
    return success

def gratuitous_next_hop(route, path):
    path_nodes = path[1:]
    route_nodes = route.split(";")

    if len(path_nodes) >= len(route_nodes):
        print("Msgrouting: Nothing left in the routes")
        return None

    for i in range(0, len(path_nodes)):
        if path_nodes[i] != route_nodes[i]:
            print(("Msgrouting: Path element %i (%s) does not match route %s" % \
                (i, path_nodes[i], route_nodes[i])))
            return None

    return route_nodes[len(path_nodes)]

def is_sendable_dest(mycall, string):
    
    # Specifically for me
    if string == mycall:
        print("Msgrouting: for me")
        return False

    # Empty string
    if not string.strip():
        print(("Msgrouting: empty: %s %s" % (string, string.strip())))
        return False

    # Is an email address:
    if "@" in string:
        print("Msgrouting: is an Email")
        return True

    # Contains lowercase characters
    if string != string.upper():
        print("Msgrouting: lowercase")
        return False

    # Contains spaces
    if string != string.split()[0]:
        print("Msgrouting: spaces")
        return False

    # Contains a gratuitous route and we're the last in line
    if ";" in string and string.split(";")[-1] == mycall:
        print("Msgrouting: End of grat")
        return False

    print("Msgrouting: default to call")

    # Looks like it's a candidate to be routed
    return True

def form_to_email(config, msgfn, replyto=None):
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

    if form.id == "email":
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
    newfn = os.path.join(config.form_store_dir(),
                         folder,
                         os.path.basename(msg))
    msg_lock(newfn)
    shutil.move(msg, newfn)
    msg_unlock(newfn)

def move_to_outgoing(config, msg):
    return move_to_folder(config, msg, "Outbox")

class MessageRoute(object):
    def __init__(self, line):
        self.dest, self.gw, self.port = line.split()

class MessageRouter(gobject.GObject):
    __gsignals__ = {
        "get-station-list" : signals.GET_STATION_LIST,
        "user-send-form" : signals.USER_SEND_FORM,
        "form-sent" : signals.FORM_SENT,
        "form-received" : signals.FORM_RECEIVED,
        "ping-station" : signals.PING_STATION,
        "event" : signals.EVENT,
        }
    _signals = __gsignals__

    def _emit(self, signal, *args):
        gobject.idle_add(self.emit, signal, *args)

    def __proxy_emit(self, signal):
        def handler(obj, *args):
            print(("Msgrouting: Proxy emit %s: %s" % (signal, args)))
            self._emit(signal, *args)
        return handler

    def __init__(self, config):
        gobject.GObject.__init__(self)

        self.__event = threading.Event()

        self.__config = config

        self.__sent_call = {}
        self.__sent_port = {}
        self.__file_to_call = {}
        self.__failed_stations = {}
        self.__pinged_stations = {}

        self.__thread = None
        self.__enabled = False

    def _get_routes(self):
        rf = self.__config.platform.config_file("routes.txt")
        try:
            f = open(rf)
            lines = f.readlines()
            f.close()
        except IOError:
            return {}

        routes = {}

        for line in lines:
            if not line.strip() or line.startswith("#"):
                continue
            try:
                dest, gw, port = line.split()
                routes[dest] = gw
            except Exception as e:
                print(("Msgrouting: Error parsing line '%s': %s" % (line, e)))

        return routes

    def _sleep(self):
        t = self.__config.getint("settings", "msg_flush")
        time.sleep(t)

    def _p(self, string):
        print(("Msgrouting: [MR] %s" % string))
        import sys
        sys.stdout.flush()

    def _get_queue(self):
        queue = {}

        qd = os.path.join(self.__config.form_store_dir(), "Outbox")
        fl = glob(os.path.join(qd, "*.xml"))
        for f in fl:
            if not msg_lock(f):
                print(("Msgrouting: Message %s is locked, skipping" % f))
                continue

            form = formgui.FormFile(f)
            call = form.get_path_dst()
            del form

            if not call:
                if msg_is_locked(f):
                    msg_unlock(f)
                continue
            elif call not in queue:
                queue[call] = [f]
            else:
                queue[call].append(f)
        
        return queue

    def _send_form(self, call, port, filename):
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

    def _route_msg(self, src, dst, path, slist, routes):
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
                print(("Msgrouting: Route for %s: %s (%s)" % (dst, route, path)))
                break
            elif "@" in dst and dst not in invalid and \
                    not ":" in dst and \
                    emailgw.validate_incoming(self.__config, src, dst):
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
            elif route != dst and route in path:
                print(("Msgrouting: Route %s in path" % route))
                invalid.append(route)
                route = None # Don't route to the same location twice
            elif self._is_station_failed(route):
                print(("Msgrouting: Route %s is failed" % route))
                invalid.append(route)
                route = None # This one is not responding lately
            elif old(route) and self._station_pinged_out(route):
                print(("Msgrouting: Route %s for %s is pinged out" % (route, dst)))
                invalid.append(route)
                route = None # This one has been pinged and isn't responding
            else:
                break # We have a route to try

        if not route:
            self._p("No route for station %s" % dst)
        elif old(route) and "@" not in route and ":" not in route:
            # This station is heard, but a long time ago.  Ping it first
            # and consider it unrouteable for now
            route_station = slist.get(route, None)
            self._station_pinged_incr(route)
            if route_station:
                self._p("Pinging stale route %s" % route)
                self._emit("ping-station", route, route_station.get_port())
            route = None
        else :
            self._station_pinged_clear(route)
            self._p("Routing message for %s to %s" % (dst, route))

        return route

    def _form_to_wl2k_em(self, dst, msgfn):
        form = formgui.FormFile(msgfn)

        if form.id != "email":
            raise Exception("WL2K support requires email type message")

        payload = form.get_field_value("message")

        call = self.__config.get("user", "callsign")
        call = "".join([x for x in call if x.isalpha()])

        attachments = []
        for name, length in form.get_attachments():
            data = form.get_attachment(name)
            attachments.append(wl2k.WinLinkAttachment(name, data))

        msg = wl2k.WinLinkMessage()
        msg.encode_message(form.get_path_src(),
                           [dst],
                           form.get_subject_string(),
                           payload,
                           attachments)

        return msg

    def _route_via_email(self, call, msgfn):
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
        if self._sent_recently(route):
            self._p("Call %s is busy" % route)
            return False

        print(slist)
        port = slist[route].get_port()
        if not self._port_free(port):
            self._p("I think port %s is busy" % port)
            return False # likely already a transfer going here so skip it

        self._p("Sending %s to %s (via %s)" % (msg, call, route))
        self._send_form(route, port, msg)

        return True

    def _route_via_wl2k(self, src, dst, msgfn):
        foo, addr = dst.split(":")
        msg = self._form_to_wl2k_em(addr, msgfn)

        def complete(thread, status, error):
            if status:
                self._emit("form-sent", -1, msgfn)
            else:
                print(("Msgrouting: Failed to send via WL2K: %s" % error))

        mt = wl2k.wl2k_auto_thread(mainapp.get_mainapp(), src, send_msgs=[msg])
        mt.connect("mail-thread-complete", complete)
        mt.connect("event", self.__proxy_emit("event"))
        mt.connect("form-received", self.__proxy_emit("form-received"))
        mt.connect("form-sent", self.__proxy_emit("form-sent"))
        mt.start()

        return True

    def _route_message(self, msg, slist, routes):
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
        plist = self.emit("get-station-list")
        slist = {}

        routes = self._get_routes()

        for port, stations in plist.items():
            for station in stations:
                slist[str(station)] = station

        for dst, callq in queue.items():
            for msg in callq:

                try:
                    routed = self._route_message(msg, slist, routes)
                except Exception:
                    utils.log_exception()
                    routed = False
    
                if not routed:
                    if msg_is_locked(msg):
                        print(("Msgrouting: unlocking message %s" % msg))
                        msg_unlock(msg)
    
    def _run(self):
        while self.__enabled:
            if self.__config.getboolean("settings", "msg_forward") or \
                    self.__event.isSet():
                print("Msgrouting: Running routing loop")
                queue = self._get_queue()

                try:
                    self._run_one(queue)
                except Exception as e:
                    utils.log_exception()
                    print("Msgrouting: Fail-safe unlocking messages in queue:")
                    for msgs in queue.values():
                        for msg in msgs:
                            print(("Msgrouting: Unlocking %s" % msg))
                            if msg_is_locked(msg):
                                msg_unlock(msg)

                self.__event.clear()
            self.__event.wait(self.__config.getint("settings", "msg_flush"))

    def trigger(self):
        if not self.__thread.isAlive():
            self.start()
        else:
            self.__event.set()

    def start(self):
        self._p("Starting message router thread")
        self.__enabled = True
        self.__event.clear()
        self.__thread = threading.Thread(target=self._run)
        self.__thread.setDaemon(True)
        self.__thread.start()

    def stop(self):
        self.__enabled = False
        self.__thread.join()

    def _update_path(self, fn, call):
        form = formgui.FormFile(fn)
        form.add_path_element(call)
        form.save_to(fn)

    def _station_succeeded(self, call):
        self.__failed_stations[call] = 0

    def _station_failed(self, call):
        self.__failed_stations[call] = self.__failed_stations.get(call, 0) + 1
        print(("Msgrouting: Fail count for %s is %i" % (call, self.__failed_stations[call])))

    def _is_station_failed(self, call):
        return self.__failed_stations.get(call, 0) >= 3

    def _station_pinged_incr(self, call):
        self.__pinged_stations[call] = self.__pinged_stations.get(call, 0) + 1
        return self.__pinged_stations[call]

    def _station_pinged_clear(self, call):
        self.__pinged_stations[call] = 0

    def _station_pinged_out(self, call):
        return self.__pinged_stations.get(call, 0) >= 3

    def form_xfer_done(self, fn, port, failed):
        self._p("File %s on %s done" % (fn, port))

        if fn and msg_is_locked(fn):
            msg_unlock(fn)

        call = self.__file_to_call.get(fn, None)
        if call and call in self.__sent_call:
            # This callsign completed (or failed) a transfer
            if failed:
                self._station_failed(call)
            else:
                self._station_succeeded(call)
                self._update_path(fn, call)

            del self.__sent_call[call]
            del self.__file_to_call[fn]

        if port in self.__sent_port:
            # This port is now open for another transfer
            del self.__sent_port[port]

