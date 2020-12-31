#!/usr/bin/python
#
# Copyright 2010 Dan Smith <dsmith@danplanet.com>
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
import os
from glob import glob

import six.moves.socketserver
import threading
import smtpd
import asyncore
import email
import random
import time
import re

if __name__ == "__main__":
    import gettext
    # pylint: disable=invalid-name
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()

from d_rats import utils
from d_rats import msgrouting
from d_rats import emailgw

def mkmsgid(callsign):
    r = random.SystemRandom().randint(0,100000)
    return "%s.%x.%x" % (callsign, int(time.time()) - 1114880400, r)

class TCPServerThread(threading.Thread):
    name = "[UNNAMEDSERVER]"

    def __init__(self, config, server, spec, handler):
        self.__server = server(spec, handler)
        self.__server.set_config(config)
        threading.Thread.__init__(self)
        self.setDaemon(True)

    def run(self):
        self.__server.serve_forever()
        print("%s Exiting" % self.name)

    def stop(self):
        self.__server.shutdown()
        print("%s Shutdown" % self.name)

class POP3Exception(Exception):
    pass

class POP3Exit(Exception):
    pass

class POP3Handler(six.moves.socketserver.StreamRequestHandler):
    def _say(self, what, error=False):
        if error:
            c = "-ERR"
        else:
            c = "+OK"

        self.wfile.write(c + " %s\r\n" % what)
        print("[POP3] %s %s" % (c, what))

    def _handle_user(self, args):
        self._say("username %s accepted" % args)
        self._user = args
        return True

    def _handle_pass(self, args):
        self._say("password accepted")
        return True

    def get_messages(self, username):
        return []

    def _handle_list(self, args):
        self._handle_stat(args)
        msgs = self.get_messages(self._user)
        index = 1
        for msg in msgs:
            print("%i %i" % (index, len(str(msg))))
            self.wfile.write("%i %i \r\n" % (index, len(str(msg))))
            index += 1
        self.wfile.write(".\r\n")
        return True

    def _handle_stat(self, args):
        msgs = self.get_messages(self._user)
        size = 0
        for i in msgs:
            size += len(str(i))
        self._say("%i %i" % (len(msgs), size))
        return False

    def _handle_retr(self, args):
        try:
            index = int(args)
        except Exception:
            utils.log_exception()
            raise POP3Exception("Invalid message number")

        m = self.get_message(index - 1)
        mstr = str(m)

        self._say("OK %i octets" % len(mstr))
        self.wfile.write(mstr + "\r\n.\r\n")
        
    def _handle_top(self, args):
        msgno, lines = args.split(" ", 1)
        
        msgno = int(msgno) - 1
        lines = int(lines)

        msg = self.get_message(msgno)
        self._say("top of message follows")
        self.wfile.write("\r\n".join(str(msg).split("\r\n")[:lines]))
        self.wfile.write("\r\n.\r\n")

    def _handle_dele(self, args):
        try:
            index = int(args)
        except Exception:
            utils.log_exception()
            raise POP3Exception("Invalid message number")

        self.del_message(index-1)
        self._say("Deleted")

    def _handle(self):
        dispatch = {
            "USER" : (("",), self._handle_user),
            "PASS" : (("USER",), self._handle_pass),
            "LIST" : (("PASS", "LIST", "STAT"), self._handle_list),
            "STAT" : (("PASS", "LIST", "STAT"), self._handle_stat),
            "RETR" : (("LIST", "STAT"), self._handle_retr),
            "TOP"  : (("LIST", "STAT"), self._handle_top),
            "DELE" : (("LIST", "STAT"), self._handle_dele),
            }

        data = self.rfile.readline().strip()
        if not data:
            raise POP3Exception("Conversation error")

        try:
            cmd, args = data.split(" ", 1)
        except:
            cmd = data
            args = ""
            
        cmd = cmd.upper()

        print("[POP3] %s %s" % (cmd, args))

        if cmd == "QUIT":
            raise POP3Exit("Goodbye")

        if cmd not in list(dispatch.keys()):
            self._say("Unsupported command `%s'" % cmd, True)
            return

        states, handler = dispatch[cmd]

        if self.state not in states:
            raise POP3Exception("Can't get there from here")

        if handler(args):
            self.state = cmd

    def handle(self):
        self.state = ""

        self._say("D-RATS waiting")

        while True:
            try:
                self._handle()
            except POP3Exit as e:
                self._say(e)
                break
            except POP3Exception as e:
                self._say(e, True)
                break
            except Exception as e:
                utils.log_exception()
                self._say("Internal error", True)
                break

class DRATS_POP3Handler(POP3Handler):
    def __init__(self, config, *args):
        self.__config = config
        print("DRATS handler")
        self.__msgcache = []
        POP3Handler.__init__(self, *args)

    def get_messages(self, user):
        if self.__msgcache:
            return self.__msgcache

        if user.upper() == self.__config.get("user", "callsign"):
            d = os.path.join(self.__config.form_store_dir(), "Inbox")
            allmsg = True
        else:
            d = os.path.join(self.__config.form_store_dir(), "Outbox")
            allmsg = False

        files = glob(os.path.join(d, "*.xml"))

        for f in files:
            msg = msgrouting.form_to_email(self.__config, f)
            if not allmsg and msg["To"] != user.upper():
                continue

            name, addr = email.utils.parseaddr(msg["From"])
            if addr == "DO_NOT_REPLY@d-rats.com":
                addr = "%s@d-rats.com" % name.upper()
                msg.replace_header("From", addr)
                del msg["Reply-To"]

            name, addr = email.utils.parseaddr(msg["To"])
            if not name and "@" not in addr:
                msg.replace_header("To", "%s@d-rats.com" % addr.upper())

            msg["X-DRATS-Source"] = f
            self.__msgcache.append(msg)

        return self.__msgcache

    def get_message(self, index):
        return self.__msgcache[index]

    def del_message(self, index):
        msg = self.__msgcache[index]
        self.__msgcache[index] = None
        fn = msg["X-DRATS-Source"]

        if os.path.exists(fn):
            msgrouting.move_to_folder(self.__config, fn, "Trash")
        else:
            raise POP3Exception("Already deleted")

class DRATS_POP3Server(six.moves.socketserver.TCPServer):
    allow_reuse_address = True

    def finish_request(self, request, client_address):
        self.RequestHandlerClass(self.__config,
                                 request, client_address, self)

    def set_config(self, config):
        self.__config = config

class DRATS_POP3ServerThread(TCPServerThread):
    name = "[POP3]"

    def __init__(self, config):
        port = config.getint("settings", "msg_pop3_port")
        print("[POP3] Starting server on port %i" % port)
        TCPServerThread.__init__(self, config, DRATS_POP3Server,
                                 ("0.0.0.0", port), DRATS_POP3Handler)
        self.setDaemon(True)

class DRATS_SMTPServer(smtpd.SMTPServer):
    def __init__(self, config):
        self.__config = config
        port = config.getint("settings", "msg_smtp_port")
        smtpd.SMTPServer.__init__(self, ("0.0.0.0", port), None)

    def process_message(self, peer, mailfrom, rcpttos, data):
        msg = email.message_from_string(data)
        if "@" in mailfrom:
            sender, foo = mailfrom.split("@", 1)
        else:
            sender = mailfrom
        sender = sender.upper()

        if not re.match("[A-Z0-9]+", sender):
            raise Exception("Sender must be alphanumeric string")

        recip = rcpttos[0]
        if recip.lower().endswith("@d-rats.com"):
            recip, host = recip.upper().split("@", 1)

        print("Sender is %s" % sender)
        print("Recip  is %s" % recip)

        mid = mkmsgid(self.__config.get("user", "callsign"))
        ffn = os.path.join(self.__config.form_store_dir(),
                           "Outbox", "%s.xml" % mid)
        print("Storing mail at %s" % ffn)

        form = emailgw.create_form_from_mail(self.__config, msg, ffn)
        form.set_path_src(sender)
        form.set_path_dst(recip)
        form.save_to(ffn)
        if msgrouting.msg_is_locked(ffn):
            msgrouting.msg_unlock(ffn)

class DRATS_SMTPServerThread(threading.Thread):
    def __init__(self, config):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.__config = config
        self.__server = None

    def run(self):
        print("[SMTP] Starting server")
        self.__server = DRATS_SMTPServer(self.__config)
        asyncore.loop(timeout=1)
        print("[SMTP] Stopped")

    def stop(self):
        if self.__server:
            self.__server.close()
        self.join()
        

def main():
    '''Main program for unit testing'''

    pop3s = DRATS_POP3Server(("localhost", 9090), DRATS_POP3Handler)
    pop3s.set_config(None)
    pop3s.serve_forever()

if __name__ == "__main__":
    main()
