#!/usr/bin/python
'''cap'''
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

# import libxml2
import six.moves.urllib.request
import six.moves.urllib.parse
import six.moves.urllib.error
import tempfile
import datetime
from lxml import etree

# importing printlog() wrapper
from .debug import printlog
try:
    from hashlib import md5
except ImportError:
    printlog("Cap", "       : Installing hashlib replacement hack")
    from .utils import ExternalHash as md5


def ev_cmp_exp(ev1, ev2):
    '''Event cmp exp'''
    if ev1.expires < ev2.expires:
        return -1
    return 1


def ev_cmp_eff(ev1, ev2):
    '''Event cmp eff'''
    if ev1.effective < ev2.effective:
        return -1
    return 1


FMT = "%Y-%m-%dT%H:%M:%S"


# pylint: disable=too-many-instance-attributes
class CAPEvent():
    '''CAP Event'''
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

    def from_lxml_node(self, infonode):
        '''From lxml node'''
        for child in infonode.getchildren():
            content = child.text.strip()

            if child.id in ["effective", "expires"]:
                content = datetime.datetime.strptime(content,
                                                     "%Y-%m-%dT%H:%M:%S")

            if child.id in list(self.__dict__.keys()):
                self.__dict__[child.name] = content

    def __str__(self):
        return "%s (%s): %.20s..." % (self.headline,
                                      self.expires.strftime(FMT),
                                      self.description)

    def report(self):
        '''report'''
        return """
%s (%s - %s)
%s
""" % (self.headline,
       self.effective.strftime(FMT),
       self.expires.strftime(FMT),
       self.description)


class CAPParser():
    '''CAP Parser'''

    def __init__(self, filename):
        doc = etree.parse(filename)

        root = doc.children

        self.events = []

        hashes = []

        child = root.children
        while child:
            if child.name == "info":
                try:
                    event = CAPEvent()
                    event.from_lxml_node(child)

                    md5_hash = md5()
                    md5_hash.update(event.description)

                    if md5_hash.digest() not in hashes:
                        self.events.append(event)
                        hashes.append(md5_hash.digest())

                # pylint: disable=broad-except
                except Exception as err:
                    printlog("Unable to parse CAP node: %s (%s)" %
                             (child.name, err))

            child = child.next

        self.events.sort(ev_cmp_eff)

    def expired_events(self):
        '''Expired Events'''
        return sorted([x for x in self.events
                       if x.expires < datetime.datetime.now()],
                      ev_cmp_eff)

    def unexpired_events(self):
        '''Unexpired Events'''
        return sorted([x for x in self.events
                       if x.expires > datetime.datetime.now()],
                      ev_cmp_eff)

    def events_expiring_after(self, date):
        '''Events Expiring After'''
        return sorted([x for x in self.events if x.expires > date],
                      ev_cmp_eff)

    def events_effective_after(self, date):
        '''Events Effective After'''
        return sorted([x for x in self.events if x.effective > date],
                      ev_cmp_eff)


class CAPParserURL(CAPParser):
    '''CAP Parse URL'''

    def __init__(self, url):
        tmpf = tempfile.NamedTemporaryFile()
        name = tmpf.name
        tmpf.close()

        six.moves.urllib.request.urlretrieve(url, name)

        CAPParser.__init__(self, name)


def main():
    '''Unit Test'''

    #cp = CAPParser(sys.argv[1])
    capp = CAPParserURL("http://www.weather.gov/alerts/fl.cap")

    epoch = datetime.datetime(2008, 9, 29, 00, 59, 00)

    count = 0
    for i in capp.events_expiring_after(epoch):
        printlog((i.report()))
        count += 1

    printlog(("%i events" % count))

if __name__ == "__main__":
    main()
