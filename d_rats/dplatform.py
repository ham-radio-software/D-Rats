#!/usr/bin/python
'''D-Rats Platform'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015 Maurizio Andreotti  <iz2lxi@yahoo.it>
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
import os
import sys
import glob
import subprocess
import urllib.request
import urllib.parse
import urllib.error


if '_' not in locals():
    import gettext
    _ = gettext.gettext


class PlatformException(Exception):
    '''Generic Platform exception.'''


class NotConnectedError(PlatformException):
    '''Not connected Error.'''


class Platform():
    '''
    Platform.

    :param basepath: Configuration data directory
    :type basepath: str
    '''
    logger = logging.getLogger("Platform")

    def __init__(self, basepath):
        self.set_config_dir(basepath)
        my_dir = os.path.realpath(os.path.dirname(__file__))
        self._sys_data = os.path.dirname(my_dir)
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
        a will have a parameter with "prefix" in its name and be named
        "share"

        :returns: Directory for built in application data.
        :rtype: str
        '''
        # Known prefixes for linux based programs
        # python programs generally expect this convention even on
        # Microsoft Windows.
        # /usr - programs installed by official packages
        # /opt - programs installed from tarballs and some third party packages
        # /usr/local - Non official programs installed by system owner
        # <path> - programs installed by pip.  While pip does install into
        # the /usr path by default, that is considered a very bad practice,
        # as it can interfere with official packages.
        if '/lib/' in __file__:
            my_prefix = __file__.split('/lib/')
            my_share = os.path.join(my_prefix[0], 'share', 'd-rats')
            if os.path.exists(my_share):
                # Using standard location or a VENV
                return my_share
        # punt, assume running from source
        return self._sys_data

    def source_dir(self):
        '''
        The system application data directory.

        To be deprecated as name does not match the purpose.

        :returns: Directory for built in application data.
        :rtype: str
        '''
        return self.sys_data()

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

    def open_text_file(self, _path):
        '''
        Open Text File.

        :param _path: Path to file
        :type _path: str
        :raises: :class:`NotImplementedError`
        '''
        # This is wrong.
        # GTK should have a built in cross platform method to open
        # text file, and that should be called instead of this
        # method to open the file in a safe (read-only/no-macros) manor.
        raise NotImplementedError("The base class can't do that")

    def open_html_file(self, _path):
        '''
        Open HTML File

        :param _path: Path to file
        :type _path: str
        :raises: :class:`NotImplementedError`
        '''
        # This is wrong.
        # GTK Should have a built in cross platform method to open
        # a web browser to an HTML or JPG file that should be called
        # instead of this method.
        raise NotImplementedError("The base class can't do that")

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
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

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
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

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
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

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

    def play_sound(self, _soundfile):
        '''
        Play Sound.

        Reports sound is unsupported for this platform to log.
        :param _soundfile: Sound file to use
        :type _soundfile: str
        '''
        self.logger.info("play_sound: Sound is unsupported on this platform!")


class UnixPlatform(Platform):
    '''
    Unix Platform.

    :param basepath: Path to store the configuration file,
                     default "~/.d-rats-ev"
    :type basepath: str
    '''
    logger = logging.getLogger("UnixPlatform")

    def __init__(self, basepath):
        self.set_config_dir(basepath)
        Platform.__init__(self, basepath)

    def set_config_dir(self, basepath):
        '''
        Set the base directory.

        :param basepath: Base directory
        :type basepath: str
        '''
        if not basepath:
            basepath = os.path.abspath(os.path.join(self.default_dir(),
                                                    ".d-rats-ev"))
        if not os.path.isdir(basepath):
            os.mkdir(basepath)
        self._base = basepath

    def default_dir(self):
        '''
        Default Directory.

        :returns: Default directory path
        :rtype: str
        '''
        return os.path.abspath(os.getenv("HOME"))

    @staticmethod
    def filter_filename(filename):
        '''
        Filter Filename.

        :param filename: Source filename
        :type filename: str
        :returns: filename adjusted for platform
        :rtype: str
        '''
        return filename.replace("/", "")

    def _unix_doublefork_run(self, *args):
        pid1 = os.fork()
        if pid1 == 0:
            pid2 = os.fork()
            if pid2 == 0:
                self.logger.info("Exec'ing %s", str(args))
                os.execlp(args[0], *args)
            else:
                sys.exit(0)
        else:
            os.waitpid(pid1, 0)
            self.logger.info("Exec child exited")

    def open_text_file(self, path):
        '''
        Open Text File for editing.

        :param path: Path to text file
        :type path: str
        '''
        # pylint: disable=fixme
        # todo find and replace calls with GTK function.
        self.logger.info("open_text_file: received order"
                         " to open in gedit %s s", path)
        self.logger.info("If after this message your linux box crashes, "
                         "please install gedit")
        self._unix_doublefork_run("gedit", path)

    def open_html_file(self, path):
        '''
        Open HTML file in Firefox.

        :param path: Path of file to open
        :type path: str
        '''
        # pylint: disable=fixme
        # todo find and replace calls with GTK function.
        self.logger.info("open_html_file:"
                         " received order to open in firefox %s", path)
        self.logger.info("If after this message your linux box crashes, "
                         "please install firefox")
        self._unix_doublefork_run("firefox", path)

    def list_serial_ports(self):
        '''
        List Serial Ports.

        :returns: The serial ports
        :rtype: list of str
        '''
        return sorted(glob.glob("/dev/ttyS*") + glob.glob("/dev/ttyUSB*"))

    def os_version_string(self):
        '''
        OS Version String.

        :returns: a version string for the OS
        :rtype: str
        '''
        # There should be a more portable way to get the version string.
        try:
            issue = open("/etc/issue.net", "r")
            ver = issue.read().strip()
            issue.close()
            ver = "%s - %s" % (os.uname()[0], ver)
        except IOError as err:
            if err.errno == 2: # No such file or directory
                # Linux use of this file seems to be deprecated.
                pass
            ver = " ".join(os.uname())
        return ver

    @staticmethod
    def run_sync(command):
        '''
        Run Sync.

        :param command: Command to run.
        :type command: str
        :returns: Command status and output
        :rtype: tuple[int, str]
        '''
        return subprocess.getstatusoutput(command)

    def play_sound(self, soundfile):
        '''
        Play Sound.

        :param soundfile: Sound file to try.
        :rtype: str
        '''
        import ossaudiodev
        import sndhdr

        try:
            (file_type, rate, channels, _f, bits) = sndhdr.what(soundfile)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("play_sound: Unable to determine"
                             "sound header of %s: broad-exception",
                             soundfile, exc_info=True)
            return

        if file_type != "wav":
            self.logger.info("play_sound: Unable to play non-wav file %s",
                             soundfile)
            return

        if bits != 16:
            self.logger.info("play_sound: Unable to support strange"
                             "non-16-bit audio (%i)", bits)
            return

        dev = None
        try:
            dev = ossaudiodev.open("w")
            dev.setfmt(ossaudiodev.AFMT_S16_LE)
            dev.channels(channels)
            dev.speed(rate)

            file_handle = open(soundfile, "rb")
            dev.write(file_handle.read())
            file_handle.close()

            dev.close()
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("play_sound: Error playing sound %s: %s",
                             soundfile, "broad-exception", exc_info=True)

        if dev:
            dev.close()


class MacOSXPlatform(UnixPlatform):
    '''
    Mac OSX Platform.

    :param basepath: path to the configuration directory
    :type basepath: str
    '''

    def __init__(self, basepath):
        self.logger = logging.getLogger("MacOSXPlatform")
        # We need to make sure DISPLAY is set
        if "DISPLAY" not in os.environ:
            self.logger.info("Forcing DISPLAY for MacOS")
            os.environ["DISPLAY"] = ":0"

        os.environ["PANGO_RC_FILE"] = "../Resources/etc/pango/pangorc"

        UnixPlatform.__init__(self, basepath)

    def open_html_file(self, path):
        '''
        Open HTML File.

        :param path: file to open
        :type path: str
        '''
        self._unix_doublefork_run("open", path)

    def open_text_file(self, path):
        '''
        Open Text File for edit.

        :param path: Path to textfile
        :type path: str
        '''
        macos_textedit = "/Applications/TextEdit.app/Contents/MacOS/TextEdit"
        self._unix_doublefork_run(macos_textedit, path)

    def list_serial_ports(self):
        '''
        List Serial Ports.

        :returns: serial port names
        :rtype: list[str]
        '''
        keyspan = glob.glob("/dev/cu.KeySerial*")
        prolific = glob.glob("/dev/tty.usbserial*")

        return sorted(keyspan + prolific)

    def os_version_string(self):
        '''
        OS Version String.

        :returns: "MacOS X"
        :rtype: str
        '''
        return "MacOS X"

    def sys_data(self):
        '''
        The system application data directory.

        The system application data directory is used to locate the
        built in constant data for an application, and this will be
        assumed to be a read only directory after installation is complete.

        For most projects the packaging procedure and install will have
        a will have a parameter with "prefix" in its name to set this
        directory.

        :returns: Directory for built in application data.
        :rtype: str
        '''
        # See the Unix platform class for more details
        # Since many developers do not have MacOSX this needs
        # some diagnostics if it does not work.
        if '/lib/' in __file__:
            my_prefix = __file__.split('/lib/')
            my_share = os.path.join(my_prefix[0], 'share', 'd-rats')
            if os.path.exists(my_share):
                # Using standard location or a VENV
                return my_share
            mac_prefix = '../Resources'
            if os.path.exists(os.path.join('mac_prefix', 'ui')):
                return mac_prefix
            self.logger.info('Can not find d-rats internal data files'
                             'Looked in %s and %s.',
                             my_share, mac_prefix)
        return self._sys_data


class Win32Platform(Platform):
    '''
    Win32 Platform.

    :param basepath, default is "%APPDATA%\\D-RATS-EV"
    :type basepath: str
    '''
    logger = logging.getLogger("Win32Platform")

    def __init__(self, basepath=None):
        self.set_config_dir(basepath)

        Platform.__init__(self, basepath)

    def set_config_dir(self, basepath):
        '''
        Set the base directory.

        :param basepath: Base directory
        :type basepath: str
        '''
        if not basepath:
            appdata = os.getenv("APPDATA")
            if not appdata:
                appdata = "C:\\"
            basepath = os.path.abspath(os.path.join(appdata, "D-RATS-EV"))

        if not os.path.isdir(basepath):
            os.mkdir(basepath)
        self._base = basepath

    def default_dir(self):
        '''
        Default Directory.

        :returns: default directory
        :rtype: str
        '''
        return os.path.abspath(
            os.path.join(os.getenv("USERPROFILE"), "Desktop"))

    def filter_filename(self, filename):
        '''
        Filter Filename.

        :param filename: filename to use
        :type filename: str
        :returns: filename filtered for platform.
        :rtype: str
        '''
        for char in "/\\:*?\"<>|":
            filename = filename.replace(char, "")

        return filename

    def open_text_file(self, path):
        '''
        Open Text File for editing.

        :param path: path of file to open
        :type path: str
        '''
        subprocess.Popen(["notepad", path])

    def open_html_file(self, path):
        '''
        Open Html File in explorer.

        :param path: Path to file
        :type path: str
        '''
        subprocess.Popen(["explorer", path])

    def list_serial_ports(self):
        '''
        List Serial Ports.

        :returns: List of serial ports
        :rtype: list[str]
        '''
        # pylint not handing cross-platform import checks
        # pylint: disable=import-error
        try:
            import win32file # type: ignore
            import pywintypes # type: ignore
            import win32con # type: ignore
        except ImportError:
            self.logger.info("Python win32api related packaging missing",
                             exc_info=True)
            return []

        ports = []
        for i in range(1, 257):
            try:
                portname = "COM%i" % i
                mode = win32con.GENERIC_READ | win32con.GENERIC_WRITE
                port = \
                    win32file.CreateFile(portname,
                                         mode,
                                         win32con.FILE_SHARE_READ,
                                         None,
                                         win32con.OPEN_EXISTING,
                                         0,
                                         None)
                ports.append(portname)
                win32file.CloseHandle(port)
                port = None

            except pywintypes.error as err:
                # Error code 5 Apparently if the serial port is in use.
                if err.args[0] not in [2, 5]:
                    self.logger.info("list_serial_ports", exc_info=True)

        return ports

    def gui_open_file(self, start_dir=None):
        '''
        GUI open file.

        :param start_dir: Directory to start in, default None
        :type start_dir: str
        :returns: Filename to open or none.
        :rtype: str
        '''
        # pylint not handing cross-platform import checks
        # pylint: disable=import-error
        try:
            import win32gui # type: ignore
            import pywintypes # type: ignore
        except ImportError:
            self.logger.info("Python win32api related packaging missing",
                             exc_info=True)
            return None

        try:
            fname, _filter, __flags = win32gui.GetOpenFileNameW()
        except pywintypes.error as err:
            self.logger.info("gui_open_file: Failed to get filename: %s", err)
            return None
        return str(fname)

    def gui_save_file(self, start_dir=None, default_name=None):
        '''
        GUI Save File.

        :param start_dir: directory to start in, default None
        :type default_name: str
        :param default_name: Default name of file, default None.
        :type default_name: str
        :returns: filename to save to or None
        :rtype: str
        '''
        # pylint not handing cross-platform import checks
        # pylint: disable=import-error
        try:
            import win32gui # type: ignore
            import pywintypes # type: ignore
        except ImportError:
            self.logger.info("Python win32api related packaging missing",
                             exc_info=True)
            return None

        try:
            fname, _filter, _flags = \
                win32gui.GetSaveFileNameW(File=default_name)
        except pywintypes.error as err:
            self.logger.info("gui_save_file: Failed to get filename: %s", err)
            return None
        return str(fname)

    def gui_select_dir(self, start_dir=None):
        '''
        GUI Select Dir.

        :param start_dir: directory to start in, default None
        :type start_dir: str
        :returns: selected directory or None
        :rtype: str
        '''
        # pylint not handing cross-platform import checks
        # pylint: disable=import-error
        try:
            from win32com.shell import shell # type: ignore
            import pywintypes # type: ignore
        except ImportError:
            self.logger.info("Python win32com related packaging missing",
                             exc_info=True)
            return None

        try:
            err = "No error detected"
            pidl, _display_name, _ilmage_list = shell.SHBrowseForFolder()
        except pywintypes.com_error as err:
            pidl = None
        if not pidl:
            self.logger.info("gui_select_dir: failed to get directory: %s", err)
            return None
        fname = shell.SHGetPathFromIDList(pidl)
        if not isinstance(fname, str):
            fname = fname.decode('utf-8', 'replace')
        return str(fname)

    def os_version_string(self):
        '''
        Os Version String.

        :returns: Platform version string
        :rtype: str
        '''
        # pylint not handing cross-platform import checks
        # pylint: disable=import-error, unused-import
        try:
            import win32api # type: ignore
        except ImportError:
            self.logger.info("os_version_string: Failed to load win32api",
                             exc_info=True)
            return "Windows Unknown."
        # platform: try to identify Microsoft Windows version
        vers = {"11.0": "Windows 11",
                "10.0": "Windows 10",
                "6.2": "Windows 8->10",
                "6.1": "Windows 7",
                "6.0": "Windows Vista",
                "5.2": "Windows XP 64-Bit",
                "5.1": "Windows XP",
                "5.0": "Windows 2000",
               }
        # pylint not handing cross-platform import checks
        # pylint: disable=undefined-variable
        (major_version, minor_version, _build_number, _platform_id, _version) \
            = win32api.GetVersionEx() # type: ignore
        return vers.get(str(major_version) + "." + str(minor_version),
                        "Win32 (Unknown %i.%i)" %
                        (major_version, minor_version)) + \
                        " " + str(win32api.GetVersionEx()) # type: ignore

    def play_sound(self, soundfile):
        '''
        Play Sound.

        :param soundfile: file to play sound from
        :type soundfile: str
        '''
        # pylint not handing cross-platform import checks
        # pylint: disable=import-error
        import winsound

        winsound.PlaySound(soundfile, winsound.SND_FILENAME)


def _get_platform(basepath):
    if os.name == "nt":
        return Win32Platform(basepath)
    if sys.platform == "darwin":
        return MacOSXPlatform(basepath)
    return UnixPlatform(basepath)


PLATFORM = None


def get_platform(basepath=None):
    '''
    Get Platform.

    :param basepath: configuration file path, default None
    :returns: platform information
    :rtype: :class:`Platform`
    '''

    # pylint: disable=global-statement
    global PLATFORM

    if not PLATFORM:
        PLATFORM = _get_platform(basepath)

    return PLATFORM


def do_test():
    '''Unit Test.'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)

    logger = logging.getLogger("dplatform")
    pform = get_platform()

    logger.info("Config dir: %s", pform.config_dir())
    logger.info("Default dir: %s", pform.default_dir())
    logger.info("Log file (foo): %s", pform.log_file("foo"))
    logger.info("Serial ports: %s", pform.list_serial_ports())
    logger.info("OS Version: %s", pform.os_version_string())
    logger.info("Built_in_data: %s", pform.sys_data())

    if len(sys.argv) > 1:

        pform.open_text_file("d-rats.py")

        logger.info("Open file: %s", pform.gui_open_file())
        logger.info("Save file: %s",
                    pform.gui_save_file(default_name="Foo.txt"))
        logger.info("Open folder: %s", pform.gui_select_dir("/tmp"))


if __name__ == "__main__":
    do_test()
