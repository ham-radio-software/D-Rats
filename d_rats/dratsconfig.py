# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2021-2023 John. E. Malmberg - Python3 Conversion
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

'''D-Rats Configuration Data Module.'''

import os
import logging
import configparser

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf  # type: ignore


if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .config_defaults import DEFAULTS
from .dplatform import Platform


# pylint wants only 7 ancestors, we can not to anything about that.
# pylint: disable=too-many-ancestors
class DratsConfig(configparser.ConfigParser):
    '''
    D-Rats Configuration.

    This class is a Singleton so that it can be
    accessed as a global variable instead of needing
    to be passed.
    '''
    _instance = None
    logger = logging.getLogger("DratsConfig")
    _inited = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(DratsConfig, cls).__new__(cls)
        else:
            cls._inited = True
        return cls._instance

    def __init__(self):
        if self._inited:
            return
        configparser.ConfigParser.__init__(self)

        self.platform = Platform.get_platform()
        self.filename = self.platform.config_file("d-rats.config")

        self.logger.info("File %s", self.filename)
        self.read(self.filename)
        self.widgets = []

        self.set_defaults()

        # create "D-RATS Shared" folder for file transfers
        if self.get("prefs", "download_dir") == ".":
            default_dir = os.path.join(self.platform.default_dir(),
                                       "D-RATS Shared")
            self.logger.info("%s", default_dir)
            if not os.path.exists(default_dir):
                self.logger.info("Creating directory for downloads: %s",
                                 default_dir)
                os.makedirs(default_dir, exist_ok=True)
                self.set("prefs", "download_dir", default_dir)

        # create the folder structure for storing the map tiles
        map_dir = self.get("settings", "mapdir")
        if not os.path.exists(map_dir):
            self.logger.info("Creating directory for maps: %s", map_dir)
            os.makedirs(map_dir, exist_ok=True)
        if not os.path.exists(os.path.join(map_dir, "base")):
            os.makedirs(os.path.join(map_dir, "base"), exist_ok=True)
        if not os.path.exists(os.path.join(map_dir, "cycle")):
            os.makedirs(os.path.join(map_dir, "cycle"), exist_ok=True)
        if not os.path.exists(os.path.join(map_dir, "outdoors")):
            os.makedirs(os.path.join(map_dir, "outdoors"), exist_ok=True)
        if not os.path.exists(os.path.join(map_dir, "landscape")):
            os.makedirs(os.path.join(map_dir, "landscape"), exist_ok=True)

    def set_defaults(self):
        '''
        Set Defaults.

        Set default value if not already present
        '''
        for sec, opts in DEFAULTS.items():
            if not self.has_section(sec):
                self.add_section(sec)

            for opt, value in opts.items():
                if not self.has_option(sec, opt):
                    self.set(sec, opt, value)

    def save(self):
        '''Save Configuration.'''
        file_handle = open(self.filename, "w")
        self.write(file_handle)
        file_handle.close()

    # This is an intentional method override.
    # pylint: disable=arguments-differ, arguments-renamed
    def getboolean(self, sec, key):
        '''
        Get Boolean value.

        :param sec: Section of parameter file
        :type sec: str
        :param key: Key in section
        :type key: str
        :returns: Boolean value
        :rtype: bool
        '''
        try:
            return configparser.ConfigParser.getboolean(self, sec, key,
                                                        fallback=False)
        except ValueError:
            self.logger.debug("Failed to get boolean: %s/%s", sec, key)
            return False

    # This is an intentional method override.
    # pylint: disable=arguments-differ
    def getint(self, sec, key):
        '''
        Temporary override for getint.

        Code should be using getint_tolerant.
        '''
        return self.getint_tolerant(sec, key)

    def getint_tolerant(self, section, key):
        '''
        Get Integer, tolerate errors.

        :param section: Section of parameter file
        :type section: str
        :param key: Key in section
        :type key: str
        :returns: integer value.
        :rtype: int
        '''
        ret_val = 0
        try:
            ret_val = configparser.ConfigParser.getint(self, section, key)
        except ValueError:
            ret_val_str = configparser.ConfigParser.get(self, section, key)
            self.logger.debug(
                "Error in config file: %s/%s data %s is not an int",
                section, key, ret_val_str)
            ret_val = int(float(ret_val_str))
        return ret_val

    def form_source_dir(self):
        '''
        Form Source Directory.

        Directory is created if if does not exist.

        :returns: Form storage directory
        :rtype: str
        '''
        form_dir = os.path.join(self.platform.config_dir(), "Form_Templates")
        if not os.path.isdir(form_dir):
            os.makedirs(form_dir, exist_ok=True)

        return form_dir

    def form_store_dir(self):
        '''
        Form Store directory.

        Directory is created if it does not exist.

        :returns: Form storage directory
        :rtype: str
        '''
        form_dir = os.path.join(self.platform.config_dir(), "messages")
        if not os.path.isdir(form_dir):
            os.makedirs(form_dir, exist_ok=True)

        return form_dir

    def ship_obj_fn(self, name):
        '''
        Ship Object Filename.

        :param name: Filename for object
        :type name: str
        :returns: Path for object
        :rtype: str
        '''
        return os.path.join(self.platform.sys_data(), name)

    def ship_img(self, name):
        '''
        Ship Image.

        :param name: Name of the image file
        :type name: str
        :returns: GdkPixbuf of image
        :rtype: :class:`GdkPixbuf.Pixbuf`
        '''
        path = self.ship_obj_fn(os.path.join("images", name))
        return GdkPixbuf.Pixbuf.new_from_file(path)


def main():
    '''Main package for testing.'''
    # pylint: disable=import-outside-toplevel
    import sys
    sys.path.insert(0, ".")

    logging.basicConfig(level=logging.INFO)

    # Each class should have their own logger.
    logger = logging.getLogger("config_test")

    logger.info("sys.path=%s", sys.path)
    # mm: fn = "/home/dan/.d-rats/d-rats.config"
    filename = "d-rats.config"

    parser = configparser.ConfigParser()
    parser.read(filename)

if __name__ == "__main__":
    main()
