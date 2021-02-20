#!/usr/bin/python
'''Weather Update?'''
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
import os

import six.moves.urllib.request
import six.moves.urllib.parse
import six.moves.urllib.error
from lxml import etree

class InvalidXMLError(Exception):
    '''Invalid XML Error'''

WEATHER_KEYS = [
    "temperature_string", "temp_f", "temp_c",
    "relative_humidity",
    "wind_string", "wind_dir", "wind_degrees", "wind_mph", "wind_gust_mph",
    "pressure_string", "pressure_mb", "pressure_in",
    "dewpoint_in", "dewpoint_f", "dewpoint_c",
    "heat_index_string", "heat_index_f", "heat_index_c",
    "windchill_string", "windchill_f", "windchill_c",
    "precip_1hr_string", "precip_1hr_in", "precip_1hr_metric",
    "precip_today_string", "precip_today_in", "precip_today_metric",
]

class WUObservation():
    '''WU Observation'''

    def __init__(self):
        self.location = {}
        self.station_id = None
        self.time = None
        self.staton_id = None
        self.weather = {}

    def __str__(self):
        return "%s: %s (%s)" % (self.location["full"],
                                self.weather["temperature_string"],
                                self.time)

    def __parse_location(self, node):
        child = node.children
        while child:
            self.location[child.name] = child.getContent()
            child = child.next

    def __parse_doc(self, doc):
        root = doc.children

        if root.name != "current_observation":
            raise InvalidXMLError("Root is not current_observation")

        child = root.children
        while child:
            if child.name in ["location", "observation_location"]:
                self.__parse_location(child)
            elif child.name == "station_id":
                self.staton_id = child.getContent()
            elif child.name == "observation_time_rfc822":
                try:
                    self.time = datetime.datetime.strptime(\
                        child.getContent(),
                        "%a, %d %B %Y %H:%M:%S %Z")
                # pylint: disable=bare-except
                except:
                    self.time = child.getContent()
            elif child.name in WEATHER_KEYS:
                self.weather[child.name] = child.getContent()

            child = child.next

    def from_xml(self, xml):
        '''From xml'''
        doc = etree.fromstring(xml)
        return self.__parse_doc(doc)

    def from_uri(self, uri):
        '''From Uri'''
        file_name, _something = six.moves.urllib.request.urlretrieve(uri)
        doc = etree.parse(file_name)
        os.remove(file_name)
        return self.__parse_doc(doc)
