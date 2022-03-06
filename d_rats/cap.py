#!/usr/bin/python
'''Common Alert Protocol.'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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
import urllib.request
import tempfile
from datetime import datetime, timezone
from functools import cmp_to_key
from hashlib import md5
from lxml import etree

# Planned for deprecation, used only if hashlib.md5 import fails.
# from .utils import ExternalHash as md5


def ev_cmp_exp(ev1, ev2):
    '''
    Event compare expires Time.

    :param ev1: Event 1
    :type ev1: :class:`CAPEvent`
    :param ev2: Event 2
    :type ev1: :class:`CAPEvent`
    :returns: -1 if ev1 expires is older, 1 if not
    :rtype: int
    '''
    if ev1.expires < ev2.expires:
        return -1
    return 1


def ev_cmp_eff(ev1, ev2):
    '''
    Event compare effective time.

    :param ev1: Event 1
    :type ev1: :class:`CAPEvent`
    :param ev2: Event 2
    :type ev1: :class:`CAPEvent`
    :returns: -1 if ev1 effective is older, 1 if not
    :rtype: int
    '''
    if ev1.effective < ev2.effective:
        return -1
    return 1


FMT = "%Y-%m-%dT%H:%M:%S"


# pylint: disable=too-many-instance-attributes
class CAPEvent():
    '''CAP Event'''

    def __init__(self):
        self.logger = logging.getLogger("CAPParser")
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
        for child in infonode.iterchildren():
            if not child.text:
                continue
            content = child.text.strip()
            child_id = child.tag.split('}')[1]
            if child_id == 'title':
                child_id = 'headline'
            elif child_id == 'summary':
                child_id = 'description'
            if child_id in ["effective", "expires"]:
                try:
                    content = datetime.strptime(content, "%Y-%m-%dT%H:%M:%S%z")
                except ValueError:
                    self.logger.info("from_lxml_node: unable to parse %s: %s",
                                     child_id, content, exc_info=True)
                    content = datetime.now(tz=timezone.utc)
            if child_id in list(self.__dict__.keys()):
                self.__dict__[child_id] = content

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
    '''
    CAP Parser.

    :param filename: Filename to parse
    :type filename: str
    '''

    def __init__(self, filename):
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger("CAPParser")
        doc = etree.parse(filename)

        root = doc.getroot()
        print("root", type(root))

        self.events = []

        hashes = []

        for child in root.iterchildren("{*}entry"):
            event = CAPEvent()
            event.from_lxml_node(child)
            md5_hash = md5()
            description = event.description.encode('utf-8', 'replace')
            md5_hash.update(description)

            if md5_hash.digest() not in hashes:
                self.events.append(event)
                hashes.append(md5_hash.digest())

        self.events.sort(key=cmp_to_key(ev_cmp_eff))

    def expired_events(self):
        '''
        Expired Events.

        :returns: sorted expired events
        :rtype: list of :class:`CAPEvent`
        '''
        now = datetime.now(tz=timezone.utc)
        return sorted([x for x in self.events if x.expires < now],
                      key=cmp_to_key(ev_cmp_eff))

    def unexpired_events(self):
        '''
        Unexpired Events.

        :returns: sorted unexpired events
        :rtype: list of :class:`CAPEvent`
        '''
        now = datetime.now(tz=timezone.utc)
        return sorted([x for x in self.events if x.expires > now],
                      key=cmp_to_key(ev_cmp_eff))

    def events_expiring_after(self, date):
        '''
        Events Expiring After date.

        :param date: Date expiration change
        :type date: float
        :returns: sorted expiring events
        :rtype: list of :class:`CAPEvent`
        '''
        return sorted([x for x in self.events if x.expires > date],
                      key=cmp_to_key(ev_cmp_eff))

    def events_effective_after(self, date):
        '''
        Events Effective After date.

        :param date: Date event is effective
        :type date: float
        :returns: sorted effective events
        :rtype: list of :class:`CAPEvent`
        '''
        return sorted([x for x in self.events if x.effective > date],
                      key=cmp_to_key(ev_cmp_eff))


class CAPParserURL(CAPParser):
    '''
    CAP Parse URL.

    :param url: URL to read for parsing.
    :type url: str
    '''

    def __init__(self, url):
        self.logger = logging.getLogger("CAPParserUrl")
        tmpf = tempfile.NamedTemporaryFile()
        name = tmpf.name
        tmpf.close()

        urllib.request.urlretrieve(url, name)

        CAPParser.__init__(self, name)


def main():
    '''Unit Test.'''

    logging.basicConfig(
        format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level='INFO')

    logger = logging.getLogger("CAP_Test")

    #cp = CAPParser(sys.argv[1])
    #capp = CAPParserURL("http://www.weather.gov/alerts/fl.cap")
    capp = CAPParserURL("https://alerts.weather.gov/cap/us.php?x=0")

    epoch = datetime(2008, 9, 29, 00, 59, 00, 00, timezone.utc)

    count = 0
    for i in capp.events_expiring_after(epoch):
        logger.info((i.report()))
        count += 1

    logger.info("%i events", count)

if __name__ == "__main__":
    main()
