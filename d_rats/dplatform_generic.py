'''D-Rats Platform Generic.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015 Maurizio Andreotti  <iz2lxi@yahoo.it>
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

import logging
import os
import shutil
import subprocess
import sys

# Need all of these packages for sound to work on a generic platform
# The pydub package not currently available on msys2 mingw64.
from contextlib import contextmanager
HAVE_AUDIO = False
if not os.name == "nt":
    try:
        from pydub import AudioSegment
        from pydub.playback import play
        # pylint: disable=unused-import
        import pyaudio  # Just verifying it is installed.
        HAVE_AUDIO = True
    except ModuleNotFoundError:
        pass

import urllib.request
import urllib.parse
import urllib.error

import gi  # type: ignore # Needed for pylance on Microsoft Windows
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk # type: ignore
from gi.repository import Gio # type: ignore


if '_' not in locals():
    import gettext
    _ = gettext.gettext


class PlatformException(Exception):
    '''Generic Platform exception.'''


class NotConnectedError(PlatformException):
    '''Not connected Error.'''


# Unfortunately play(sound) may have some log noise
# that it should be suppressing.
@contextmanager
def suppress_stderr():
    '''Suppress stderr temporarily.'''
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    sys.stderr.flush()
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)


# pylint wants only 20 public methods.
# pylint: disable=too-many-public-methods
class PlatformGeneric():
    '''
    Generic Platform.

    :param basepath: Configuration data directory
    :type basepath: str
    '''
    logger = logging.getLogger("Platform")
    my_class = None

    def __init__(self, basepath):
        self.set_config_dir(basepath)
        my_dir = os.path.realpath(os.path.dirname(__file__))
        self._base_dir = os.path.dirname(my_dir)
        self._sys_data = None
        if os.path.exists(os.path.join(self._base_dir, '.git')):
            # We need to know if we are running from a git checkout, in that
            # case we want to use the data from the git checkout directory
            # instead of data from an package install.
            self._sys_data = self._base_dir
        self._connected = True

    def __str__(self):
        text = ["Platform %s:" % str(self.__class__.__name__)]
        text.append("  configuration:       %s" % self.config_dir())
        text.append("  system_data: %s" % self.sys_data())
        text.append("  OS version: %s" % self.os_version_string())

        return os.linesep.join(text)

    def set_config_dir(self, basepath):

        '''
        Set the configuration directory.

        :param basepath: Configuration directory
        :type basepath: str
        '''
        self._base = basepath

    def config_dir(self):
        '''
        Config Directory.

        :returns: configuration directory
        :rtype: str
        '''
        return self._base

    def sys_data(self):
        '''
        The system application data directory.

        The system application data directory is used to locate the
        built in constant data for an application, and this will be
        assumed to be a read only directory after installation is complete.

        For most projects the packaging procedure and install will have
        a parameter with "prefix" in its name and be named "share"

        :returns: Directory for built in application data.
        :rtype: str
        '''
        # Known prefixes for linux based programs
        # python programs generally expect this convention even on
        # Microsoft Windows.
        # /usr - programs installed by official packages
        # /opt - programs installed from tarballs and some third party packages
        # /usr/local - Non official programs installed by system owner
        # <path> - programs installed by pip.  While pip does install into the
        #          /usr path by default, that is considered a very bad practice,
        #          as it can interfere with official packages.
        if self._sys_data:
            return self._sys_data
        if '/lib/' in __file__:
            my_prefix = __file__.split('/lib/')
            my_share = os.path.join(my_prefix[0], 'share', 'd-rats')
            if os.path.exists(my_share):
                # Using standard location or a VENV
                self._sys_data = my_share
                return self._sys_data
        # punt, assume running from source
        self._sys_data = self._base_dir
        return self._sys_data

    @staticmethod
    def get_exe_path(name):
        '''
        Get the absolute path for an executable program.

        :param name: Name of executable program
        :type name: str
        :returns: Path to the executable program.
        :rtype: str
        '''
        # Make trivial check from the normal paths
        exe_path = shutil.which(name)
        if exe_path:
            return exe_path
        programfiles = os.getenv("PROGRAMFILES")
        if programfiles:
            for program in [programfiles, programfiles + " (x86)"]:
                test_path=os.path.join(program, name)
                exe_path = shutil.which(name, path=test_path)
                if exe_path:
                    return exe_path
        return None

    def log_dir(self):
        '''
        Log Directory

        :returns: Log directory
        :rtype: str
        '''
        logdir = os.path.join(self.config_dir(), "logs")
        if not os.path.isdir(logdir):
            os.mkdir(logdir)

        return logdir

    @staticmethod
    def filter_filename(filename):
        '''
        Filter Filename.

        :param filename: filename passed in
        :type filename: str
        :returns: filename passed in adjusted for platform if needed
        :rtype: str
        '''
        return filename

    def log_file(self, filename):
        '''
        Log file.

        :param filename: filename template
        :type filename: str
        :returns: Log file path
        :rtype: str
        '''
        filename = self.filter_filename(filename + ".txt").replace(" ", "_")
        return os.path.join(self.log_dir(), filename)

    def config_file(self, filename):
        '''
        Config File.

        :returns: Configuration file path
        :rtype: str
        '''
        return os.path.join(self.config_dir(),
                            self.filter_filename(filename))

    @staticmethod
    def open_text_file(path):
        '''
        Open Text File.

        :param path: Path to file
        :type _path: str
        '''
        content = Gio.content_type_from_mime_type('text/plain')
        appinfo = Gio.app_info_get_default_for_type(content, False)
        gio_path = Gio.File.parse_name(path)
        appinfo.launch([gio_path], None)

    @staticmethod
    def open_html_file(path):
        '''
        Open HTML File

        :param path: Path to file
        :type path: str
        '''
        content = Gio.content_type_from_mime_type('text/html')
        appinfo = Gio.app_info_get_default_for_type(content, False)
        gio_path = Gio.File.parse_name(path)
        appinfo.launch([gio_path], None)

    @staticmethod
    def list_serial_ports():
        '''
        List Serial Ports.

        :returns: empty list
        :rtype: list
        '''
        return []

    @staticmethod
    def default_dir():
        '''
        Default Directory.

        :returns: '.'
        :rtype: str
        '''
        return "."

    @staticmethod
    def gui_open_file(start_dir=None):
        '''
        GUI Open File.

        :param start_dir: Directory to start in, default None
        :type start_dir: str
        :returns: Filename or None
        :rtype: str
        '''
        dlg = Gtk.FileChooserDialog(
            title="Select a file to open",
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(_("Cancel"),
                        Gtk.ResponseType.CANCEL,
                        _("Open"), Gtk.ResponseType.OK)
        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK:
            return fname
        return None

    @staticmethod
    def gui_save_file(start_dir=None, default_name=None):
        '''
        GUI Save File.

        :param start_dir: Directory to start in, default None
        :type start_dir: str
        :param default_name: Default filename, default None
        :type default_name: str
        :returns: Filename to save or None
        :rtype: str
        '''
        dlg = Gtk.FileChooserDialog(
            title="Save file as",
            action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons(_("Cancel"),
                        Gtk.ResponseType.CANCEL,
                        _("Save"), Gtk.ResponseType.OK)
        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        if default_name:
            dlg.set_current_name(default_name)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK:
            return fname
        return None

    @staticmethod
    def gui_select_dir(start_dir=None):
        '''
        Gui Select Directory.

        :param start_dir: Directory to start in, default None
        :type start_dir: str
        :returns: Directory selected or None
        :rtype: str
        '''
        dlg = Gtk.FileChooserDialog(
            title="Choose folder",
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        dlg.add_buttons(_("Cancel"),
                        Gtk.ResponseType.CANCEL,
                        _("Save"),
                        Gtk.ResponseType.OK)

        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK and os.path.isdir(fname):
            return fname
        return None

    @staticmethod
    def os_version_string():
        '''
        OS Version String.

        :returns: "Unknown Operating System"
        :rtype: str
        '''
        return "Unknown Operating System"

    @staticmethod
    def run_sync(command):
        '''
        Run Sync.

        :param command: Command to run and wait for
        :type command: str
        :returns: Command standard output in second member of tuple
        :rtype: tuple[int, str]
        '''
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE)
        data = pipe.stdout.read()
        data_str = data.decode('utf-8', 'replace')

        return 0, data_str

    def retrieve_url(self, url):
        '''
        Retrieve URL.

        :param url: Url to retrieve if connected.
        :type url: str
        :raises: :class:`NotConnectedError`: if not connected
        :returns: Data from URL
        '''
        if self._connected:
            return urllib.request.urlretrieve(url)

        raise NotConnectedError("Not connected")

    def set_connected(self, connected):
        '''
        Set Connected.

        :param connected: New connected state
        :type connected: bool
        '''
        self._connected = connected

    @staticmethod
    def have_sound():
        '''
        Do we have sound support?

        :returns: Status of sound support
        :rytpe: bool
        '''
        return HAVE_AUDIO

    def play_sound(self, soundfile):
        '''
        Play Sound.

        Reports sound is unsupported for this platform to log.
        :param soundfile: Sound file to use
        :type soundfile: str
        '''
        if not HAVE_AUDIO:
            self.logger.info("play_sound: "
                             "pydub and pyaudio not installed!")

        sound = AudioSegment.from_wav(soundfile)
        with suppress_stderr():
            play(sound)
