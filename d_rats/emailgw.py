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
#importing printlog() wrapper
from .debug import printlog

import os
import threading
import poplib
import smtplib
import email
from six.moves import range
try:
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
except ImportError:
    # Python 2.4
    from email import MIMEMultipart
    from email import MIMEBase
    from email import MIMEText 

import rfc822
import time
from . import dplatform
import gobject
import re
import random

from . import formgui
from .ui import main_events
from . import signals
from . import utils
from . import msgrouting


def create_form_from_mail(config, mail, tmpfn):
    subject = mail.get("Subject", "[no subject]")
    sender = mail.get("From", "Unknown <devnull@nowhere.com>")
    
    xml = None
    body = ""

    if mail.is_multipart():
        html = None
        for part in mail.walk():
            if part.get_content_maintype() == "multipart":
                continue
            elif part.get_content_type() == "d-rats/form_xml":
                xml = str(part.get_payload())
                break # A form payload trumps all
            elif part.get_content_type() == "text/plain":
                body += part.get_payload(decode=True)
            elif part.get_content_type() == "text/html":
                html = part.get_payload(decode=True)
        if not body:
            body = html
    else:
        body = mail.get_payload(decode=True)

    if not body and not xml:
        raise Exception("Unable to find a usable part")

    messageid = mail.get("Message-ID", time.strftime("%m%d%Y%H%M%S"))
    if not msgrouting.msg_lock(tmpfn):
        printlog("AIEE: Unable to lock incoming email message file!")

    if xml:
        f = open(tmpfn, "w")
        f.write(xml)
        f.close()
        form = formgui.FormFile(tmpfn)
        recip = form.get_recipient_string()
        if "%" in recip:
            recip, addr = recip.split("%", 1)
            recip = recip.upper()
    else:
        printlog("Email from %s: %s" % (sender, subject))

        recip, addr = rfc822.parseaddr(mail.get("To", "UNKNOWN"))

        efn = os.path.join(config.form_source_dir(), "email.xml")
        form = formgui.FormFile(efn)
        form.set_field_value("_auto_sender", sender)
        form.set_field_value("recipient", recip)
        form.set_field_value("subject", "EMAIL: %s" % subject)
        form.set_field_value("message", utils.filter_to_ascii(body))
        form.set_path_src(sender.strip())
        form.set_path_dst(recip.strip())
        form.set_path_mid(messageid)

    form.save_to(tmpfn)

    return form

class MailThread(threading.Thread, gobject.GObject):
    __gsignals__ = {
        "user-send-chat" : signals.USER_SEND_CHAT,
        "user-send-form" : signals.USER_SEND_FORM,
        "form-received" : signals.FORM_RECEIVED,
        "get-station-list" : signals.GET_STATION_LIST,
        "event" : signals.EVENT,
        "mail-thread-complete" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                                  (gobject.TYPE_BOOLEAN, gobject.TYPE_STRING)),
        }

    _signals = __gsignals__

    def _emit(self, signal, *args):
        gobject.idle_add(self.emit, signal, *args)

    def __init__(self, config, host, user, pasw, port=110, ssl=False):
        threading.Thread.__init__(self)
        gobject.GObject.__init__(self)
        self.setDaemon(True)

        self.username = user
        self.password = pasw
        self.server = host
        self.port = port
        self.use_ssl = ssl

        self.config = config

        self._coerce_call = None

    def message(self, message):
        printlog("[MAIL %s@%s] %s" % (self.username, self.server, message))

    def create_form_from_mail(self, mail):
        id = self.config.get("user", "callsign") + \
            time.strftime("%m%d%Y%H%M%S") + \
            mail.get("Message-id", str(random.randint(0, 1000)))
        mid = dplatform.get_platform().filter_filename(id)
        ffn = os.path.join(self.config.form_store_dir(),
                           _("Inbox"),
                           "%s.xml" % mid)
        try:
            form = create_form_from_mail(self.config, mail, ffn)
        except Exception as e:
            printlog("Failed to create form from mail: %s" % e)
            return    

        if self._coerce_call:
            printlog("Coercing to %s" % self._coerce_call)
            form.set_path_dst(self._coerce_call)
        else:
            printlog("Not coercing")
    
        form.add_path_element("EMAIL")
        form.add_path_element(self.config.get("user", "callsign"))
        form.save_to(ffn)
    
        self._emit("form-received", -999, ffn)
    
    def fetch_mails(self):
        self.message("Querying %s:%i" % (self.server, self.port))

        if self.use_ssl:
            server = poplib.POP3_SSL(self.server, self.port)
        else:
            server = poplib.POP3(self.server, self.port)

        server.user(self.username)
        server.pass_(self.password)
        
        num = len(server.list()[1])

        messages = []

        for i in range(num):
            self.message("Fetching %i/%i" % (i+1, num))
            result = server.retr(i+1)
            server.dele(i+1)
            message = email.message_from_string("\r\n".join(result[1]))
            messages.append(message)

        server.quit()

        return messages

    def run(self):
        self.message("One-shot thread starting")
        mails = None

        if not self.config.getboolean("state", "connected_inet"):
            result = "Not connected to the Internet"
        else:
            try:
                mails = self.fetch_mails()
            except Exception as e:
                result = "Failed (%s)" % e

            if mails:
                for mail in mails:
                    self.create_form_from_mail(mail)
                event = main_events.Event(_("Received %i messages") % \
                                              len(mails))
                self._emit("event", event)

                result = "Queued %i messages" % len(mails)
            elif mails is not None:
                result = "No messages"

        self.message("Thread ended [ %s ]" % result)

        self._emit("mail-thread-complete", mails != None, result)

class CoercedMailThread(MailThread):
    def __init__(self, *args):
        call = str(args[-1])
        args = args[:-1]
        MailThread.__init__(self, *args)
        self._coerce_call = call

class AccountMailThread(MailThread):
    def __init__(self, config, account):
        settings = config.get("incoming_email", account)

        try:
            host, user, pasw, poll, ssl, port, action, enb = \
                settings.split(",", 7)
        except ValueError:
            raise Exception("Unable to parse account settings for `%s'" % \
                                account)

        actions = {
            _("Form") : self.create_form_from_mail,
            _("Chat") : self.do_chat_from_mail,
            }

        try:
            self.__action = actions[action]
        except KeyError:
            raise Exception("Unsupported action `%s' for %s@%s" % \
                                (action, user, host))

        ssl = ssl == "True"
        if not port:
            port = ssl and 995 or 110
        else:
            port = int(port)

        self._poll = int(poll)

        self.event = threading.Event()
        self.enabled = enb == "True"

        MailThread.__init__(self, config, host, user, pasw, port, ssl)

    def do_chat_from_mail(self, mail):
        if mail.is_multipart():
            body = None
            for part in mail.walk():
                html = None
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True)
                    break
                elif part.get_content_type() == "text/html":
                    html = part.get_payload(decode=True)
            if not body:
                body = html
        else:
            body = mail.get_payload()

        text = "Message from %s (%s):\r\n%s" % (\
            mail.get("From", "Unknown Sender"),
            mail.get("Subject", ""),
            body)
            
        for port in self.emit("get-station-list").keys():
            self._emit("user-send-chat", "CQCQCQ", port, text, False)

        event = main_events.Event(None,
                                  "Mail received from %s and sent via chat" % \
                                      mail.get("From", "Unknown Sender"))
        self._emit("event", event)

    def run(self):
    #removing the connection check as it was always failing, need to sort the scope of the variable
 #        if self.config.getboolean("state", "connected_inet"): 
            mails = []
            try:
                mails = self.fetch_mails()
            except Exception as e:
                self.message("Failed to retrieve messages: %s" % e)
            for mail in mails:
                self.__action(mail)
            if mails:
                event = main_events.Event(None,
                                          "Received %i email(s)" % len(mails))
                self._emit("event", event)  
                
      #      else:
       #         self.message("Not connected")

        
class PeriodicAccountMailThread(AccountMailThread):
    def run(self):
        self.message("Periodic thread starting")

        while self.enabled:
            AccountMailThread.run(self)
            self.event.wait(self._poll * 60)
            self.event.clear()

        self.message("Thread ending")

    def trigger(self):
        self.event.set()

    def stop(self):
        self.enabled = False
        self.trigger()

def __validate_access(config, callsign, emailaddr, types):
    rules = config.options("email_access")

    for rule in rules:
        rulespec = config.get("email_access", rule)
        call, access, filter = rulespec.split(",", 2)

        if call in [callsign, "*"] and re.search(filter, emailaddr):
            #print "%s -> %s matches %s,%s,%s" % (callsign, emailaddr,
            #                                     call, access, filter)
            #print "Access types allowed: %s" % types
            return access in types
        #else:
            #print "%s -> %s does not match %s,%s,%s" % (callsign, emailaddr,
            #                                            call, access, filter)

    printlog("No match found")

    return False

def validate_outgoing(config, callsign, emailaddr):
    return __validate_access(config, callsign, emailaddr, ["Both", "Outgoing"])
    
def validate_incoming(config, callsign, emailaddr):
    return __validate_access(config, callsign, emailaddr, ["Both", "Incoming"])

if __name__ == "__main__":
    class fakeout(object):
        form_source_dir = "forms"
        form_store_dir = "."

        def reg_form(self, *args):
            pass

        def list_add_form(self, *args, **kwargs):
            pass

        def get_stamp(self):
            return "FOO"

    mt = MailThread(None, fakeout())
    mt.run()
