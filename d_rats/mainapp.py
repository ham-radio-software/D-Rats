#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com> 
# review 2015 Maurizio Andreotti  <iz2lxi@yahoo.it>
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

#importing printlog() wrapper
from .debug import printlog

import sys
from . import dplatform
import os


# this to generate timestamps associated to GPS fixes  
from time import gmtime, strftime

debug_path = dplatform.get_platform().config_file("debug.log")
if sys.platform == "win32" or not os.isatty(0):
    sys.stdout = open(debug_path, "w", 0)
    sys.stderr = sys.stdout
    printlog("Mainapp","  : Enabled debug log for Win32 systems")
else:
    try:
        os.unlink(debug_path)
    except OSError:
        pass

# gettext module provides message translation and catalog management
import gettext
# load the basic d-rats labels - it will load the localized translation later
gettext.install("D-RATS")

#import various libraries of support functions
import time
import re
from threading import Thread, Lock
from select import select
import socket
from commands import getstatusoutput
import glob
import shutil
import datetime

import serial
import gtk     #to manage windows objects
import gobject #to manage multitasking

#these modules are imported from the d_rats folder
from . import mainwindow
from . import config
from . import gps
from . import mapdisplay
from . import map_sources
from . import comm
from . import sessionmgr
from . import session_coordinator
from . import emailgw
from . import formgui
from . import station_status
from . import pluginsrv
from . import msgrouting
from . import wl2k
from . import inputdialog
from . import version
from . import agw
from . import mailsrv


from .ui import main_events

from .utils import filter_to_ascii,NetFile,log_exception,run_gtk_locked
from .utils import init_icon_maps
from .sessions import rpc, chat, sniff


# lets init the basic functions of the mainapp module
init_icon_maps()
LOGTF = "%m-%d-%Y_%H:%M:%S"
MAINAPP = None

# inizialize the multitasking for gtk (required to manage events in gtk windows and background activities)
gobject.threads_init()


def ping_file(filename):
# checks if the file passed as parameter can be opened
    try:
        f = NetFile(filename, "r")
    except IOError as e:
        raise Exception("Unable to open file %s: %s" % (filename, e))
        return None

    data = f.read()
    f.close()

    return data

def ping_exec(command):
# checks if the command passed as parameter can be opened
    s, o = getstatusoutput(command)
    if s:
        raise Exception("Failed to run command: %s" % command)
        return None
    return o

class CallList(object):
    def __init__(self):
        self.clear()

    def clear(self):
        self.data = {}

    def set_call_pos(self, call, pos):
        (t, _) = self.data.get(call, (0, None))

        self.data[call] = (t, pos)

    def set_call_time(self, call, ts=None):
        if ts is None:
            ts = time.time()

        (foo, p) = self.data.get(call, (0, None))

        self.data[call] = (ts, p)

    def get_call_pos(self, call):
        (foo, p) = self.data.get(call, (0, None))
        return p

    def get_call_time(self, call):
        (t, foo) = self.data.get(call, (0, None))
        return t

    def list(self):
        return list(self.data.keys())

    def is_known(self, call):
        return call in self.data

    def remove(self, call):
        try:
            del self.data[call]
        except:
            pass

class MainApp(object):

  
    def callback_gps(self, lat, lng, station="", comments=""):

        # this is to communicate the gps fixes to the D-Rats Web Map standalone program
        #load server ip and port
        mapserver_ip = self.config.get("settings", "mapserver_ip")
        mapserver_port = int(self.config.get("settings", "mapserver_port"))

        # this class broadcasts the gps fixes to the web browsers
        flat = float(lat)
        flng = float(lng)

        # Prepare string to broadcast to internet browsers clients
        message = '{ "lat": "%f", "lng": "%f", "station": "%s", "comments": "%s","timestamp": "%s"  }' % (flat, flng, station, comments, strftime("%Y-%m-%d %H:%M:%S", gmtime()))
        printlog("Mainapp","   : preparing our gpsfix in JSON :", message)
        
      
        try:
            #create an AF_INET, STREAM socket (TCP)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            printlog("Mainapp","   :  Failed to create socket. Error code: " + str(msg[0]) + " , Error message : " + msg[1])
            raise
        printlog("Mainapp","  :  Socket Created")

        #Connect to remote server
        printlog("Mainapp","   :  Connecting to: ", mapserver_ip, ":", mapserver_port)
        try:
            #create an AF_INET, STREAM socket (TCP)
            s.connect((mapserver_ip , mapserver_port))
            
            printlog("Mainapp","   : message to send:", message)
            try :
               #Set the whole string
                s.sendall(message)
                s.close
            except socket.error as msg:
                #Send failed
                printlog("Mainapp","   :  Send failed of:", message)
                sys.exit()

            printlog("Mainapp","    :  Message sent successfully")  
            
        except socket.error as msg:
            printlog("Mainapp","    :  Failed to create socket. Error code: " + str(msg[0]) + " , Error message : " + msg[1])
            s.close()
            s = None
        printlog("Mainapp","   :  Socket Created")

    def setup_autoid(self):
        idtext = "(ID)"

    def stop_comms(self, portid):
        if portid in self.sm:
            sm, sc = self.sm[portid]
            sm.shutdown(True)
            sc.shutdown()
            del self.sm[portid]

            portspec, pipe = self.__pipes[portid]
            del self.__pipes[portid]
            self.__unused_pipes[portspec] = pipe

            return True
        else:
            return False

    def _make_socket_listeners(self, sc):
        forwards = self.config.options("tcp_out")
        for forward in forwards:
            try:
                sport, dport, station = \
                    self.config.get("tcp_out", forward).split(",")
                sport = int(sport)
                dport = int(dport)
            except Exception as e:
                printlog("Mainapp","   : Failed to parse TCP forward config %s: %s" % (forward, e))
                return

            try:
                sc.create_socket_listener(sport, dport, station)
                printlog("Mainapp","   : Started socket listener %i:%i@%s" % \
                    (sport, dport, station))
            except Exception as e:
                printlog("Mainapp","   : Failed to start socket listener %i:%i@%s: %s" % \
                    (sport, dport, station, e))

    def start_comms(self, portid, conninet):
        #load from the "ports" config the line related to portid
        spec = self.config.get("ports", portid)
        try:
            #try getting the config params from splitting the config line
            enb, port, rate, dosniff, raw, name = spec.split(",")
            enb = (enb == "True")           #means port is enabled
            dosniff = (dosniff == "True")   #means traffic sniffing to be active
            raw = (raw == "True")           #means raw to be active
        except Exception as e:
            printlog("Mainapp","   : Failed to parse portspec %s:" % spec)
            log_exception()
            return

        if not enb:
            #if port not enabled, and was already active, let's cancel it
            if name in self.sm:
                del self.sm[name]
                printlog("Mainapp","   : startcomms: deleted port %s (%s)" % (portid, name))

            return

        printlog("Mainapp","   : startcomms: Starting port %s (%s)" % (portid, name))

        call = self.config.get("user", "callsign")
        
        #configure path depending port type and parameters
        if port in self.__unused_pipes:
            path = self.__unused_pipes[port]
            del self.__unused_pipes[port]
            printlog("Mainapp","   : deleted unused pipe %s for port %s" % (path, port))
        elif port.startswith("tnc-ax25:"):
            printlog("Mainapp","   : Port %s as tnc-ax25" %  port)
            tnc, _port, tncport, path = port.split(":")
            path = path.replace(";", ",")
            _port = "%s:%s" % (_port, tncport)
            path = comm.TNCAX25DataPath((_port, int(rate), call, path))
        elif port.startswith("tnc:"):
            printlog("Mainapp","   : Port %s as tnc" %  port)
            _port = port.replace("tnc:", "")
            path = comm.TNCDataPath((_port, int(rate)))
        elif port.startswith("dongle:"):
            printlog("Mainapp","   : Port %s as Dongle" %  port)
            path = comm.SocketDataPath(("127.0.0.1", 20003, call, None))
        elif port.startswith("agwpe:"):
            path = comm.AGWDataPath(port, 0.5)
            printlog("Mainapp","   : Opening AGW: %s" % portid)
        #ratflector case
        elif ":" in port:          
            #if internet connection is set to False, lets skip activating this port
            
            printlog("Mainapp","   : Ratflector Port=%s with internet connectivy=%s" %  (portid, conninet))
            if not conninet:
                   printlog("Mainapp","   : Skipping port %s with internet connectivy=%s" %  (portid, conninet)) 
                   return
            try:    
                (mode, host, sport) = port.split(":")
            except ValueError:
                event = main_events.Event(None,
                                          _("Failed to connect to") +    \
                                                  " %s: " % port + \
                                                  _("Invalid port string"))
                self.mainwindow.tabs["event"].event(event)
                return False
            path = comm.SocketDataPath((host, int(sport), call, rate))
            printlog("Mainapp","   : path set to=%s" %  path) 
        #last option is serial line
        else:
            path = comm.SerialDataPath((port, int(rate)))

        if name in self.__pipes:
            raise Exception("Port %s already started!" % name)
        self.__pipes[name] = (port, path)

        def transport_msg(msg):
            _port = name
            event = main_events.Event(None, "%s: %s" % (_port, msg))
            gobject.idle_add(self.mainwindow.tabs["event"].event, event)

        transport_args = {
            "compat" : raw,
            "warmup_length" : self.config.getint("settings", "warmup_length"),
            "warmup_timeout" : self.config.getint("settings", "warmup_timeout"),
            "force_delay" : self.config.getint("settings", "force_delay"),
            "msg_fn" : transport_msg,
            }

        if name not in self.sm:
            #if we are not chatting 1-to-1 let's do CQ 
            sm = sessionmgr.SessionManager(path, call, **transport_args)

            chat_session = sm.start_session("chat",
                                            dest="CQCQCQ",
                                            cls=chat.ChatSession)
            self.__connect_object(chat_session, name)

            rpcactions = rpc.RPCActionSet(self.config, name)
            self.__connect_object(rpcactions)

            rpc_session = sm.start_session("rpc",
                                           dest="CQCQCQ",
                                           cls=rpc.RPCSession,
                                           rpcactions=rpcactions)

            def sniff_event(ss, src, dst, msg, port):
                #here print the sniffed traffic into the event tab
                if dosniff:
                    event = main_events.Event(None, "Sniffer: %s" % msg)
                    self.mainwindow.tabs["event"].event(event)

                #in any case let's print the station heard into stations tab 
                self.mainwindow.tabs["stations"].saw_station(src, port)

            ss = sm.start_session("Sniffer",
                                  dest="CQCQCQ",
                                  cls=sniff.SniffSession)
            sm.set_sniffer_session(ss._id)
            ss.connect("incoming_frame", sniff_event, name)

            sc = session_coordinator.SessionCoordinator(self.config, sm)
            self.__connect_object(sc, name)

            sm.register_session_cb(sc.session_cb, None)

            self._make_socket_listeners(sc)

            self.sm[name] = sm, sc

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
            sm, sc = self.sm[name]

            sm.set_comm(path, **transport_args)
            sm.set_call(call)

        return True

    def chat_session(self, portname):
        return self.sm[portname][0].get_session(lid=1)

    def rpc_session(self, portname):
        return self.sm[portname][0].get_session(lid=2)

    def sc(self, portname):
        return self.sm[portname][1]

    def check_comms_status(self):
        #added in 0.3.10
        printlog("Mainapp","   : CHECK PORTS STATUS ")
        printlog("Mainapp","   : Ports expected to be already started:")
        for portid in self.sm.keys():
            printlog("Mainapp","    ->   %s" % portid)
        
        printlog("Mainapp","   : Checking all Ports from config:")          
        for portid in self.config.options("ports"):
            printlog("Mainapp","   : portid %s" % portid)
                               
            #load from the "ports" config the line related to portid
            spec = self.config.get("ports", portid)
            try:
                #try getting the config params from splitting the config line
                enb, port, rate, dosniff, raw, name = spec.split(",")
                enb = (enb == "True")           #means port is enabled
                dosniff = (dosniff == "True")   #means traffic sniffing to be active
                raw = (raw == "True")           #means raw to be active
            except Exception as e:
                printlog("Mainapp","   : Failed to parse portspec %s:" % spec)
                log_exception()
                return
            
            if name in self.__pipes:
                printlog("Mainapp","   : Port %s already started!" % name)
            else:
                printlog("Mainapp","   : Port %s not started" % name)
            

    def check_stations_status(self):    
        #added in 0.3.10        
        printlog("Mainapp","   : Check stations")
        station_list = self.emit("get-station-list")
        stations = []
        for portlist in station_list.values():
            stations += [str(x) for x in portlist]
            station, port = prompt_for_station(stations, self._config)
            printlog("Mainapp","   : Station %s resulting on port %s" % station, port)
           
    def _refresh_comms(self, conn):    
        printlog("Mainapp","   : REFRESHING COMMS invoked with conninet=%s " % conn)
        
        if (conn == ""): 
            #this case of "" happens when invoked at start up and conninet is not passed but shall read from config file
            # although this should always working, reading this value from config file works only at startup, 
            # so it needed to be passed within the event signal
            conninet = self.config.getboolean("state","connected_inet") 
            printlog("Mainapp","   : Conninet value changed from emptystring with getboolean to: %s " % conn)
       
        #Validate the boolean identity of the received conn
        if (conn == "True"):
                conninet = True
        if (conn == True):
                conninet = True
        else:
                conninet = False    
        printlog("Mainapp","   :  verify  :-------------------- Conninet=%s " % conninet)
        
        #lets first delete all comms in place
        delay = False       
        for portid in self.sm.keys():
            printlog("Mainapp","   : Stopping %s" % portid)
            if self.stop_comms(portid):
                if sys.platform == "win32":
                    # Wait for windows to let go the serial port
                    delay = True
        if delay:
            time.sleep(0.25)
        
        #lets restart all needed comms, skipping ratfactors if conninet=False
        for portid in self.config.options("ports"):
            printlog("Mainapp","   : Re-Starting %s" % portid)
            self.start_comms(portid,conninet)

        for spec, path in self.__unused_pipes.items():
            printlog("Mainapp","   : Path %s for port %s no longer needed" % (path, spec))
            path.disconnect()

        self.__unused_pipes = {}

        ### avoid checking status to speed up 
        ### self.check_comms_status()
        #self.check_stations_status()
 
    def _static_gps(self):
        #inizialize the variables to store our local position data fetched from configuration
        lat = 0.0
        lon = 0.0
        alt = 0.0
        call = ""

        try:
            #load static data from configuration 
            lat = self.config.get("user", "latitude")
            lon = self.config.get("user", "longitude")
            alt = self.config.get("user", "altitude")
            call = self.config.get("user", "callsign")
            mapserver_active = self.config.get("settings", "mapserver_active")

        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stdout)
            printlog("Mainapp","   : Invalid static position: %s" % e)

        printlog("Mainapp","   : Configuring the Static position: %s,%s" % (lat,lon))

        # Call the mapserver to update our position sweeper  
        if mapserver_active == "True":
            printlog("Mainapp","   : Mapserver active:", mapserver_active, "call: ", call)
            self.callback_gps(lat, lon, call, "altitude: "+alt)
        else:
            printlog("Mainapp","   : Mapserver not active: %s, call:; %s" % (mapserver_active, call))
        return gps.StaticGPSSource(lat, lon, alt)

    def _refresh_gps(self):
        port = self.config.get("settings", "gpsport")
        rate = self.config.getint("settings", "gpsportspeed")
        enab = self.config.getboolean("settings", "gpsenabled")

        printlog('Mainapp', "   : GPS: %s on %s@%i" % (enab, port, rate))

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
        for k, v in self.mail_threads.items():
            v.stop()
            del self.mail_threads[k]

        accts = self.config.options("incoming_email")
        for acct in accts:
            data = self.config.get("incoming_email", acct)
            if data.split(",")[-1] != "True":
                continue
            try:
                t = emailgw.PeriodicAccountMailThread(self.config, acct)
            except Exception:
                log_exception()
                continue
            self.__connect_object(t)
            t.start()
            self.mail_threads[acct] = t

        try:
            if self.config.getboolean("settings", "msg_smtp_server"):
                smtpsrv = mailsrv.DRATS_SMTPServerThread(self.config)
                smtpsrv.start()
                self.mail_threads["SMTPSRV"] = smtpsrv
        except Exception as e:
            printlog("Mainapp","   : Unable to start SMTP server: %s" % e)
            log_exception()

        try:
            if self.config.getboolean("settings", "msg_pop3_server"):
                pop3srv = mailsrv.DRATS_POP3ServerThread(self.config)
                pop3srv.start()
                self.mail_threads["POP3SRV"] = pop3srv
        except Exception as e:
            printlog("Mainapp","   : Unable to start POP3 server: %s" % e)
            log_exception()

    def _refresh_lang(self):
        #load the localized labels
        locales = { "English" : "en",
                    "German" : "de",
                    "Italiano" : "it",
                    "Dutch" : "nl",
                    }
        locale = locales.get(self.config.get("prefs", "language"), "English")
        printlog("Mainapp","   : Loading locale `%s'" % locale)

        localedir = os.path.join(dplatform.get_platform().source_dir(),
                                 "locale")
        printlog("Mainapp","   : Locale dir is: %s" % localedir)

        if "LANGUAGE" not in os.environ:
            os.environ["LANGUAGE"] = locale

        try:
            lang = gettext.translation("D-RATS",
                                       localedir=localedir,
                                       languages=[locale])
            lang.install()
            gtk.glade.bindtextdomain("D-RATS", localedir)
            gtk.glade.textdomain("D-RATS")
        except LookupError:
            printlog("Mainapp","   : Unable to load language `%s'" % locale)
            gettext.install("D-RATS")
        except IOError as e:
            printlog("Mainapp","   : Unable to load translation for %s: %s" % (locale, e))
            gettext.install("D-RATS")

    def _load_map_overlays(self):
        self.stations_overlay = None

        self.map.clear_map_sources()

        source_types = [map_sources.MapFileSource,
                        map_sources.MapUSGSRiverSource,
                        map_sources.MapNBDCBuoySource]

        for stype in source_types:
            try:
                sources = stype.enumerate(self.config)
            except Exception as e:
                from . import utils
                utils.log_exception()
                printlog("Mainapp","   : Failed to load source type %s" % stype)
                continue

            for sname in sources:
                try:
                    source = stype.open_source_by_name(self.config, sname)
                    self.map.add_map_source(source)
                except Exception as e:
                    log_exception()
                    printlog("Mainapp","   : Failed to load map source %s: %s" % \
                        (source.get_name(), e))
                if sname == _("Stations"):
                    self.stations_overlay = source

        if not self.stations_overlay:
            fn = os.path.join(self.config.platform.config_dir(),
                              "static_locations",
                              _("Stations") + ".csv")
            try:
                os.makedirs(os.path.dirname(fn))
            except:
                pass
            open(fn, "w").close()
            self.stations_overlay = map_sources.MapFileSource(_("Stations"),
                                                              "Static Overlay",
                                                              fn)


    def refresh_config_conn(self, conninet):
        printlog("Mainapp","   : Refresh_config_conn invoking refresh_comms with conninet= %s" % conninet)
        self._refresh_comms(conninet)                
         
    def refresh_config(self,conninet):
        printlog("Mainapp","   : Refreshing config with conninet= %s" % conninet) 
        #conninet is the bool value relted to the setting of internet connectivty flag in the menu
        call = self.config.get("user", "callsign")
        gps.set_units(self.config.get("user", "units"))        
        self._refresh_comms(conninet)
        self._refresh_gps()
        self._refresh_mail_threads() 
        self._refresh_map()
    
    def _refresh_map(self):
        printlog("Mainapp","   : reconfigure Mapwindow with new map, connection = ", self.config.getboolean("state","connected_inet"))
        
        #setup of the url for retrieving the map tiles depending on the preference
        if self.config.get("settings", "maptype") == "cycle":
            mapurl = self.config.get("settings", "mapurlcycle")
            mapkey = self.config.get("settings", "keyformapurlcycle")
        elif self.config.get("settings", "maptype") == "landscape":
            mapurl = self.config.get("settings", "mapurllandscape")
            mapkey = self.config.get("settings", "keyformapurllandscape")
        elif self.config.get("settings", "maptype") == "outdoors":
            mapurl = self.config.get("settings", "mapurloutdoors")
            mapkey = self.config.get("settings", "keyformapurloutdoors")
        else:
            mapurl = self.config.get("settings", "mapurlbase")
            mapkey = ""
        
        mapdisplay.set_base_dir(os.path.join(self.config.get("settings", "mapdir"), self.config.get("settings", "maptype")), mapurl, mapkey)
        
        mapdisplay.set_connected(self.config.getboolean("state","connected_inet"))
        mapdisplay.set_tile_lifetime(self.config.getint("settings","map_tile_ttl") * 3600)
        proxy = self.config.get("settings", "http_proxy") or None
        mapdisplay.set_proxy(proxy)

        self.map.set_title("D-RATS Map Window - map in use: %s" % self.config.get("settings", "maptype"))
    #	self.map.connect("reload-sources", lambda m: self._load_map_overlays())
        self.map.set_zoom(14)
        self.map.queue_draw()
        return True
    
    def _refresh_location(self):
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

        try:
            comment = self.config.get("settings", "default_gps_comment")
            fix.APRSIcon = gps.dprs_to_aprs(comment);
        except Exception as e:
            log_exception()
            fix.APRSIcon = "\?"
        self.__map_point.set_icon_from_aprs_sym(fix.APRSIcon)

        self.stations_overlay.add_point(self.__map_point)
        self.map.update_gps_status(self.gps.status_string())

        return True

    def __chat(self, src, dst, data, incoming, port):
        # here we manage the chat messages both incoming and outgoing
        if self.plugsrv:
            self.plugsrv.incoming_chat_message(src, dst, data)

        if src != "CQCQCQ":
            self.seen_callsigns.set_call_time(src, time.time())

        kwargs = {}

        if dst != "CQCQCQ":
            #so we are messaging into a private channel
            to = " -> %s:" % dst
            kwargs["priv_src"] = src
        else:
            to = ":"

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

        line = "%s%s%s %s" % (portstr, src, to, data)

        @run_gtk_locked
        def do_incoming():
            self.mainwindow.tabs["chat"].display_line(line, incoming, color,
                                                      **kwargs)

        gobject.idle_add(do_incoming)

# ---------- STANDARD SIGNAL HANDLERS --------------------

    def __status(self, object, status):
        self.mainwindow.set_status(status)       

    def __user_stop_session(self, object, sid, port, force=False):
        printlog("Mainapp","   : User did stop session %i (force=%s)" % (sid, force))
        try:
            sm, sc = self.sm[port]
            session = sm.sessions[sid]
            session.close(force)
        except Exception as e:
            printlog("Mainapp","   : Session `%i' not found: %s" % (sid, e))

    def __user_cancel_session(self, object, sid, port):
        self.__user_stop_session(object, sid, port, True)

    def __user_send_form(self, object, station, port, fname, sname):
        self.sc(port).send_form(station, fname, sname)

    def __user_send_file(self, object, station, port, fname, sname):
	self.sc(port).send_file(station, fname, sname)

    def __user_send_chat(self, object, station, port, msg, raw):
	# this event is generated by pluginsrv/send_chat function while 
	# listening from the arriving messages
	if raw:
            self.chat_session(port).write_raw(msg)
        else:
            self.chat_session(port).write(msg, station)

    def __incoming_chat_message(self, object, src, dst, data, port=None):
        if dst not in ["CQCQCQ", self.config.get("user", "callsign")]:
            # This is not destined for us
            return
        self.__chat(src, dst, data, True, port)

    def __outgoing_chat_message(self, object, src, dst, data, port=None):
        self.__chat(src, dst, data, False, port)

    def __get_station_list(self, object):
        stations = {}
        for port, (sm, sc) in self.sm.items():
            stations[port] = []

        station_list = self.mainwindow.tabs["stations"].get_stations()

        for station in station_list:
            if station.get_port() not in list(stations.keys()):
                printlog(("Mainapp   : Station %s has unknown port %s" % (station,
                                                          station.get_port())))
            else:
                stations[station.get_port()].append(station)    
        
        return stations

    def __get_message_list(self, object, station):
        return self.mainwindow.tabs["messages"].get_shared_messages(station)

    def __submit_rpc_job(self, object, job, port):
        self.rpc_session(port).submit(job)

    def __event(self, object, event):
        self.mainwindow.tabs["event"].event(event)

    def __config_changed(self, object, conninet):
        printlog("Mainapp","   : Event received: config_changed")
        conninet = self.config.getboolean("state","connected_inet") 
        self.refresh_config(conninet)
      
    def __conn_changed(self, object, conninet):
        printlog("Mainapp","   : Event received: conn_changed")
        self.refresh_config_conn(conninet)
        
    def __show_map_station(self, object, station):      
        printlog("Mainapp","    : Event received: Showing Map Window")
        self.map.show()


    def __ping_station(self, object, station, port):
        self.chat_session(port).ping_station(station)

    def __ping_station_echo(self, object, station, port,
                            data, callback, cb_data):
        self.chat_session(port).ping_echo_station(station, data,
                                                  callback, cb_data)

    def __ping_request(self, object, src, dst, data, port):
        msg = "%s pinged %s [%s]" % (src, dst, port)
        if data:
            msg += " (%s)" % data

        event = main_events.PingEvent(None, msg)
        self.mainwindow.tabs["event"].event(event)

    def __ping_response(self, object, src, dst, data, port):
        msg = "%s replied to ping from %s with: %s [%s]" % (src, dst,
                                                            data, port)
        event = main_events.PingEvent(None, msg)
        self.mainwindow.tabs["event"].event(event)

    def __incoming_gps_fix(self, object, fix, port):
        ts = self.mainwindow.tabs["event"].last_event_time(fix.station)
        if (time.time() - ts) > 300:
            self.mainwindow.tabs["event"].finalize_last(fix.station)

        fix.set_relative_to_current(self.get_position())
        event = main_events.PosReportEvent(fix.station, str(fix))
        self.mainwindow.tabs["event"].event(event)

        self.mainwindow.tabs["stations"].saw_station(fix.station, port)

        def source_for_station(station):
            s = self.map.get_map_source(station)
            if s:
                return s

            try:
                printlog(("Mainapp   :  Creating a map source for %s" % station))
                s = map_sources.MapFileSource.open_source_by_name(self.config,
                                                                  station,
                                                                  True)
            except Exception as e:
                # Unable to create or add so use "Stations" overlay
                return self.stations_overlay

            self.map.add_map_source(s)

            return s

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
        if fix.APRSIcon == None:
            point.set_icon_from_aprs_sym('\?')
            printlog("Mainapp","   : APRSIcon missing - forced to: \? ")
        else:
            point.set_icon_from_aprs_sym(fix.APRSIcon)
            
        source.add_point(point)
        source.save()
        
        #
        try:
            #load static data from configuration 
            mapserver_active = self.config.get("settings", "mapserver_active")

        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stdout)
            printlog("Mainapp","   : Invalid static position: %s" % e)

        #Send captured position to the mapserver to update our position sweeper  
        if mapserver_active == "True":
            printlog(("Mainapp   : Export to external mapserver active: %s -- sending gps fix" % mapserver_active))
            #self.callback_gps(lat, lon, call, "altitude: "+alt)
            self.callback_gps(fix.latitude, fix.longitude, station=fix.station, comments="altitude: " + str(fix.altitude))
        else:
            printlog(("Mainapp   : Export to external mapserver not active: %s" % mapserver_active))
        return gps.StaticGPSSource(fix.latitude, fix.longitude, fix.altitude)	

    
    def __station_status(self, object, sta, stat, msg, port):
        self.mainwindow.tabs["stations"].saw_station(sta, port, stat, msg)
        try:
            status = station_status.get_status_msgs()[stat]
        except KeyError:
            printlog("Mainapp","    : Invalid station_status of %d." %
                     stat)
            status="code %d" % stat

        event = main_events.Event(None,
                                  "%s %s %s %s: %s" % (_("Station"),
                                                       sta,
                                                       _("is now"),
                                                       status,
                                                       msg))
        self.mainwindow.tabs["event"].event(event)

    def __get_current_status(self, object, port):
        return self.mainwindow.tabs["stations"].get_status()

    def __get_current_position(self, object, station):
        if station is None:
            return self.get_position()
        else:
            sources = self.map.get_map_sources()
            for source in sources:
                if source.get_name() == _("stations"):
                    for point in source.get_points():
                        if point.get_name() == station:
                            fix = gps.GPSPosition(point.get_latitude(),
                                                  point.get_longitude())
                            return fix
                    break
            raise Exception("Station not found")

    def __session_started(self, object, id, msg, port):
        # Don't register Chat, RPC, Sniff
        if id and id <= 3:
            return
        elif id == 0:
            msg = "Port connected"

        printlog("Mainapp","   : [SESSION %i]: %s" % (id, msg))

        event = main_events.SessionEvent(id, port, msg)
        self.mainwindow.tabs["event"].event(event)
        return event

    def __session_status_update(self, object, id, msg, port):
        self.__session_started(object, id, msg, port)

    def __session_ended(self, object, id, msg, restart_info, port):
        # Don't register Control, Chat, RPC, Sniff
        if id <= 4:
            return

        event = self.__session_started(object, id, msg, port)
        event.set_restart_info(restart_info)
        event.set_as_final()

        fn = None
        if restart_info:
            fn = restart_info[1]

        self.msgrouter.form_xfer_done(fn, port, True)

    def __form_received(self, object, id, fn, port=None):
        if port:
            id = "%s_%s" % (id, port)

        printlog("Mainapp","   : [NEWFORM %s]: %s" % (id, fn))
        f = formgui.FormFile(fn)

        msg = '%s "%s" %s %s' % (_("Message"),
                                 f.get_subject_string(),
                                 _("received from"),
                                 f.get_sender_string())

        myc = self.config.get("user", "callsign")
        dst = f.get_path_dst()
        src = f.get_path_src()
        pth = f.get_path()

        fwd_on = self.config.getboolean("settings", "msg_forward");
        is_dst = msgrouting.is_sendable_dest(myc, dst)
        nextst = msgrouting.gratuitous_next_hop(dst, pth) or dst
        bounce = "@" in src and "@" in dst
        isseen = myc in f.get_path()[:-1]

        printlog("Mainapp","   : Decision: " + \
            "fwd:%s " % fwd_on + \
            "sendable:%s " % is_dst + \
            "next:%s " % nextst + \
            "bounce:%s " % bounce + \
            "seen:%s " % isseen)

        if fwd_on and is_dst and not bounce and not isseen:
            msg += " (%s %s)" % (_("forwarding to"), nextst)
            msgrouting.move_to_outgoing(self.config, fn)
            refresh_folder = "Outbox"
        else:
            refresh_folder = "Inbox"

        if msgrouting.msg_is_locked(fn):
            msgrouting.msg_unlock(fn)
        self.mainwindow.tabs["messages"].refresh_if_folder(refresh_folder)

        event = main_events.FormEvent(id, msg)
        event.set_as_final()
        self.mainwindow.tabs["event"].event(event)

    def __file_received(self, object, id, fn, port=None):
        if port:
            id = "%s_%s" % (id, port)
        _fn = os.path.basename(fn)
        msg = '%s "%s" %s' % (_("File"), _fn, _("Received"))
        event = main_events.FileEvent(id, msg)
        event.set_as_final()
        self.mainwindow.tabs["files"].refresh_local()
        self.mainwindow.tabs["event"].event(event)

    def __form_sent(self, object, id, fn, port=None):
        self.msgrouter.form_xfer_done(fn, port, False)
        if port:
            id = "%s_%s" % (id, port)
        printlog("Mainapp","   : [FORMSENT %s]: %s" % (id, fn))
        event = main_events.FormEvent(id, _("Message Sent"))
        event.set_as_final()

        self.mainwindow.tabs["messages"].message_sent(fn)
        self.mainwindow.tabs["event"].event(event)

    def __file_sent(self, object, id, fn, port=None):
        if port:
            id = "%s_%s" % (id, port)
        printlog(("Mainapp   : [FILESENT %s]: %s" % (id, fn)))
        _fn = os.path.basename(fn)
        msg = '%s "%s" %s' % (_("File"), _fn, _("Sent"))
        event = main_events.FileEvent(id, msg)
        event.set_as_final()
        self.mainwindow.tabs["files"].file_sent(fn)
        self.mainwindow.tabs["event"].event(event)

    def __get_chat_port(self, object):
        return self.mainwindow.tabs["chat"].get_selected_port()

    def __trigger_msg_router(self, object, account):
        if not account:
            self.msgrouter.trigger()
        elif account == "@WL2K":
            call = self.config.get("user", "callsign")
            mt = wl2k.wl2k_auto_thread(self, call)
            self.__connect_object(mt)
            mt.start()
        elif account in list(self.mail_threads.keys()):
            self.mail_threads[account].trigger()
        else:
            mt = emailgw.AccountMailThread(self.config, account)
            mt.start()

    def __register_object(self, parent, object):
        self.__connect_object(object)

# ------------ END SIGNAL HANDLERS ----------------

    def __connect_object(self, object, *args):
        for signal in object._signals.keys():
            handler = self.handlers.get(signal, None)
            if handler is None:
                pass
            #raise Exception("Object signal `%s' of object %s not known" % \
            #                        (signal, object))
            elif self.handlers[signal]:
                try:
                    object.connect(signal, handler, *args)
                except Exception:
                    printlog("Mainapp","   : Failed to attach signal %s" % signal)
                    raise

    def _announce_self(self):
        printlog("Mainapp","   : D-RATS v%s starting at %s" % (version.DRATS_VERSION, time.asctime()))
        printlog("Mainapp","   : %s " % dplatform.get_platform())
    
    def __init__(self, **args):
        self.handlers = {
            "conn-changed" : self.__conn_changed,
            "config-changed" : self.__config_changed,
            "event" : self.__event,          
            "incoming-chat-message" : self.__incoming_chat_message,
            "incoming-gps-fix" : self.__incoming_gps_fix,
            "notice" : False,
            "outgoing-chat-message" : self.__outgoing_chat_message,              
            "ping-station" : self.__ping_station,
            "ping-station-echo" : self.__ping_station_echo,
            "ping-request" : self.__ping_request,
            "ping-response" : self.__ping_response,
            "file-received" : self.__file_received,            
            "file-sent" : self.__file_sent,
            "form-received" : self.__form_received,            
            "form-sent" : self.__form_sent,
            "get-chat-port" : self.__get_chat_port,
            "get-current-status" : self.__get_current_status,
            "get-current-position" : self.__get_current_position,
            "get-message-list" : self.__get_message_list,   
            "get-station-list" : self.__get_station_list,  
            "register-object" : self.__register_object,
            "rpc-send-form" : self.__user_send_form,
            "rpc-send-file" : self.__user_send_file,
            "session-ended" : self.__session_ended,
            "session-started" : self.__session_started,            
            "session-status-update" : self.__session_status_update,
            "show-map-station" : self.__show_map_station,            
            "station-status" : self.__station_status,
            "status" : self.__status,
            "submit-rpc-job" : self.__submit_rpc_job,            
            "trigger-msg-router" : self.__trigger_msg_router,            
            "user-cancel-session" : self.__user_cancel_session,
            "user-send-chat" : self.__user_send_chat,                            
            "user-send-form" : self.__user_send_form,
            "user-send-file" : self.__user_send_file,
            "user-stop-session" : self.__user_stop_session,       
            }

        global MAINAPP
        MAINAPP = self

        self.comm = None
        self.sm = {}
        self.seen_callsigns = CallList()
        self.position = None
        self.mail_threads = {}
        self.__unused_pipes = {}
        self.__pipes = {}
        self.pop3srv = None

        self.config = config.DratsConfig(self)
        self._refresh_lang()

        self._announce_self()

        message = _("Since this is your first time running D-RATS, " +
                    "you will be taken directly to the configuration " +
                    "dialog.  At a minimum, put your callsign in the " +
                    "box and click 'Save'.  You will be connected to " +
                    "the ratflector initially for testing.")

        #if user callsign is not present, ask the user to fill in the basic info
        while self.config.get("user", "callsign") == "":
            d = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
            d.set_markup(message)
            d.run()
            d.destroy()
            if not self.config.show():
                raise Exception("User canceled configuration")
            message = _("You must enter a callsign to continue")

        #load position from config
        printlog("Mainapp","   : load position from config file")
        self.gps = self._static_gps()

        #create map instance
        printlog("Mainapp","   : create map window object-----")
        self.map = mapdisplay.MapWindow(self.config)
        self.map.set_title("D-RATS Map Window - map in use: %s" % self.config.get("settings", "maptype"))
        self.map.connect("reload-sources", lambda m: self._load_map_overlays())
        printlog("Mainapp","   : create map window object: connect object-----" ) 
        self.__connect_object(self.map)

        printlog("Mainapp","   : query local gps device to see our current position")
        pos = self.get_position()
        self.map.set_center(pos.latitude, pos.longitude)
        self.map.set_zoom(14)
        self.__map_point = None

        printlog("Mainapp","   : load main window with self config")
        self.mainwindow = mainwindow.MainWindow(self.config)
        
        printlog("Mainapp","   : connect main window")
        self.__connect_object(self.mainwindow)
        printlog("Mainapp","   : connect tabs")
        for tab in self.mainwindow.tabs.values():
            self.__connect_object(tab)
        
        printlog("Mainapp","   : invoke config refresh")
        
        conninet = self.config.getboolean("state","connected_inet") 
        self.refresh_config(conninet)
        self._load_map_overlays()
        

        if self.config.getboolean("prefs", "dosignon") and self.chat_session:
            printlog("Mainapp","   : going online")
            msg = self.config.get("prefs", "signon")
            status = station_status.STATUS_ONLINE
            for port in self.sm.keys():
                self.chat_session(port).advertise_status(status, msg)
        gobject.timeout_add(3000, self._refresh_location)

    def get_position(self):
        p = self.gps.get_position()
        p.set_station(self.config.get("user", "callsign"))
        try:
            p.set_station(self.config.get("user", "callsign"),
                          self.config.get("settings", "default_gps_comment"))
        except Exception:
            pass
        return p

    def load_static_routes(self):
        routes = self.config.platform.config_file("routes.txt")
        if not os.path.exists(routes):
            return

        f = open(routes)
        lines = f.readlines()
        lno = 0
        for line in lines:
            lno += 1
            if not line.strip() or line.startswith("#"):
                continue

            try:
                routeto, station, port = line.split()
            except Exception:
                printlog(("Mainapp   : Line %i of %s not valid" % (lno, routes)))
                continue

            self.mainwindow.tabs["stations"].saw_station(station.upper(), port)
            if port in self.sm:
                sm, sc = self.sm[port]
                sm.manual_heard_station(station)

    def clear_all_msg_locks(self):
        path = os.path.join(self.config.platform.config_dir(),
                            "messages",
                            "*",
                            ".lock*")
        for lock in glob.glob(path):
            printlog(("Mainapp   : Removing stale message lock %s" % lock))
            os.remove(lock)
    
    def main(self):
        # Copy default forms before we start
        distdir = dplatform.get_platform().source_dir()
        userdir = self.config.form_source_dir()
        dist_forms = glob.glob(os.path.join(distdir, "forms", "*.x?l"))
        for form in dist_forms:
            fname = os.path.basename(form)
            user_fname = os.path.join(userdir, fname)

            try:
                needupd = \
                    (os.path.getmtime(form) > os.path.getmtime(user_fname))
            except Exception:
                needupd = True
            if not os.path.exists(user_fname) or needupd:
                printlog("Mainapp","   : Installing dist form %s -> %s" % (fname, user_fname))
                try:
                    shutil.copyfile(form, user_fname)
                except Exception as e:
                    printlog(("Mainapp   :  AILED: %s" % e))

        self.clear_all_msg_locks()

        if len(self.config.options("ports")) == 0 and \
                self.config.has_option("settings", "port"):
            printlog("Mainapp","   : Migrating single-port config to multi-port")

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

        try:
            self.plugsrv = pluginsrv.DRatsPluginServer()
            self.__connect_object(self.plugsrv.get_proxy())
            self.plugsrv.serve_background()
        except Exception as e:
            printlog("Mainapp","   : Unable to start plugin server: %s" % e)
            self.plugsrv = None

        self.load_static_routes()

        try:
            self.msgrouter = msgrouting.MessageRouter(self.config)
            self.__connect_object(self.msgrouter)
            self.msgrouter.start()
        except Exception as e:
            log_exception()
            self.msgrouter = None

        #LOAD THE MAIN WINDOW
        printlog("Mainapp","   : load the main window")
        try:
            gtk.main()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            printlog("Mainapp","   : Got exception on close: %s" % e)

        printlog("Mainapp","   : Saving config...")
        self.config.save()

        if self.config.getboolean("prefs", "dosignoff") and self.sm:
            msg = self.config.get("prefs", "signoff")
            status = station_status.STATUS_OFFLINE 
            for port in self.sm.keys():
                self.chat_session(port).advertise_status(status, msg)

            time.sleep(2) # HACK

def get_mainapp(): 
    return MAINAPP

