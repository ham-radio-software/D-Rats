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

import libxml2
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
import tempfile
import datetime

try:
    from hashlib import md5
except ImportError:
    printlog("Installing hashlib replacement hack")
    from .utils import ExternalHash as md5

def ev_cmp_exp(ev1, ev2):
    if ev1.expires < ev2.expires:
        return -1
    else:
        return 1

def ev_cmp_eff(ev1, ev2):
    if ev1.effective < ev2.effective:
        return -1
    else:
        return 1


FMT = "%Y-%m-%dT%H:%M:%S"

class CAPEvent(object):
    def __init__(self):
        self.category = None
        self.event = None
        self.urgency = None
        self.severity = None
        self.certainty = None
        self.effective = None
        self.expires = None
        self.headline = None
        self.description = None

#    def __setattr__(self, name, val):
#        if not hasattr(self, name):
#            raise ValueError("No such attribute `%s'" % name)
#
#        self.__dict__[name] = val

    def from_libxml_node(self, infonode):
        child = infonode.children
        while child:
            content = child.getContent().strip()

            if child.name in ["effective", "expires"]:
                content = datetime.datetime.strptime(content,
                                                     "%Y-%m-%dT%H:%M:%S")

            if child.name in list(self.__dict__.keys()):
                self.__dict__[child.name] = content

            child = child.next

    def __str__(self):
        return "%s (%s): %s..." % (self.headline,
                                   self.expires.strftime(FMT),
                                   self.description[:20])

    def report(self):
        return """
%s (%s - %s)
%s
""" % (self.headline,
       self.effective.strftime(FMT),
       self.expires.strftime(FMT),
       self.description)

class CAPParser(object):
    def __init__(self, filename):
        doc = libxml2.parseFile(filename)

        root = doc.children

        self.events = []

        hashes = []

        child = root.children
        while child:
            if child.name == "info":
                try:
                    ev = CAPEvent()
                    ev.from_libxml_node(child)

                    hash = md5()
                    hash.update(ev.description)

                    if hash.digest() not in hashes:
                        self.events.append(ev)
                        hashes.append(hash.digest())

                except Exception as e:
                    printlog(("Unable to parse CAP node: %s (%s)" % (child.name, e)))

            child = child.next

        self.events.sort(ev_cmp_eff)

    def expired_events(self):
        return sorted([x for x in self.events if x.expires < datetime.datetime.now()],
                      ev_cmp_eff)

    def unexpired_events(self):
        return sorted([x for x in self.events if x.expires > datetime.datetime.now()],
                      ev_cmp_eff)

    def events_expiring_after(self, date):
        return sorted([x for x in self.events if x.expires > date],
                      ev_cmp_eff)

    def events_effective_after(self, date):
        return sorted([x for x in self.events if x.effective > date],
                      ev_cmp_eff)

class CAPParserURL(CAPParser):
    def __init__(self, url):
        tmpf = tempfile.NamedTemporaryFile()
        name = tmpf.name
        tmpf.close()

        six.moves.urllib.request.urlretrieve(url, name)

        CAPParser.__init__(self, name)

if __name__ == "__main__":
    import sys

    #cp = CAPParser(sys.argv[1])
    cp = CAPParserURL("http://www.weather.gov/alerts/fl.cap")

    epoch = datetime.datetime(2008, 9, 29, 00, 59, 00)

    c = 0
    for i in cp.events_expiring_after(epoch):
        printlog((i.report()))
        c += 1

    printlog(("%i events" % c))
        
