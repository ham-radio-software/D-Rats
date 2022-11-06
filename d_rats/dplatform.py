'''D-Rats Platform'''
# pylint wants only 1000 lines in a module
# pylint: disable=too-many-lines
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

import logging
import glob
import os
import shutil
import subprocess
import sys

if os.name == "nt":
    # There has been some problems with various Windows Python
    # implementations in the past.  Having these modules may make
    # D-Rats harder to use.  There are some hacks like manually
    # editing configuration files to allow testing.
    # The type: ignore is needed for pylance not handling cross-platform checks
    try:
        import win32api # type: ignore
    except ImportError:
        pass
    try:
        import pywintypes # type: ignore
    except ImportError:
        pass
    try:
        from win32com.shell import shell # type: ignore
    except ImportError:
        pass
    try:
        import win32con # type: ignore
    except ImportError:
        pass
    try:
        import win32file # type: ignore
    except ImportError:
        pass
    try:
        import win32gui # type: ignore
    except ImportError:
        pass
    try:
        import winsound # type: ignore
    except ImportError:
        pass
else:
    # These are optional - Need to see if they are available for Win32
    try:
        import ossaudiodev
    except ImportError:
        pass
    try:
        import sndhdr
    except ImportError:
        pass

import urllib.request
import urllib.parse
import urllib.error

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


if '_' not in locals():
    import gettext
    _ = gettext.gettext


class PlatformException(Exception):
    '''Generic Platform exception.'''


class NotConnectedError(PlatformException):
    '''Not connected Error.'''

# pylint wants only 20 public methods.
# pylint: disable=too-many-public-methods
class Platform():
    '''
    Platform.

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

    @classmethod
    def get_platform(cls, basepath=None):
        '''
        Get platform class object instance.

        There is always only one platform class instance.

        :param basepath: Optional basepath only used for first call.
        :type basepath: str
        :returns: Platform class instance
        :rtype: :class:`Platform`
        '''
        if cls.my_class:
            return cls.my_class
        cls.my_class = UnixPlatform(basepath)
        if os.name == "nt":
            cls.my_class = Win32Platform(basepath)
        elif sys.platform == "darwin":
            cls.my_class = MacOSXPlatform(basepath)
        return cls.my_class

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
        # pylint: disable=broad-except
        try:
            (file_type, rate, channels, _f, bits) = sndhdr.what(soundfile)
        except NameError:
            self.logger.info("play_sound: sndhdr or "
                             "related package not installed")
            return
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
        # pylint: disable=broad-except
        try:
            dev = ossaudiodev.open("w")
            dev.setfmt(ossaudiodev.AFMT_S16_LE)
            dev.channels(channels)
            dev.speed(rate)

            file_handle = open(soundfile, "rb")
            dev.write(file_handle.read())
            file_handle.close()

            dev.close()
        except NameError:
            self.logger.info("play_sound: ossaudiodev or "
                             "related package not installed")
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
        if self._sys_data:
            return self._sys_data
        if '/lib/' in __file__:
            my_prefix = __file__.split('/lib/')
            my_share = os.path.join(my_prefix[0], 'share', 'd-rats')
            if os.path.exists(my_share):
                # Using standard location or a VENV
                self._sys_data = my_share
                return self._sys_data
            mac_prefix = '../Resources'
            if os.path.exists(os.path.join('mac_prefix', 'ui')):
                self._sys_data = mac_prefix
                return self._sys_data
        self.logger.debug('Can not find d-rats internal data files'
                          'Looked in %s and %s.',
                          my_share, mac_prefix)
        self._sys_data = self._base_dir
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
        ports = []
        try:
            for i in range(1, 257):
                try:
                    portname = "COM%i" % i
                    mode = win32con.GENERIC_READ  # type: ignore
                    mode |= win32con.GENERIC_WRITE  # type: ignore
                    port = win32file.CreateFile(  # type: ignore
                        portname,
                        mode,
                        win32con.FILE_SHARE_READ,  # type: ignore
                        None,
                        win32con.OPEN_EXISTING,  # type: ignore
                        0,
                        None)
                    ports.append(portname)
                    win32file.CloseHandle(port)  # type: ignore
                    port = None

                except pywintypes.error as err:  # type: ignore
                    # Error code 5 Apparently if the serial port is in use.
                    if err.args[0] not in [2, 5]:
                        self.logger.info("list_serial_ports", exc_info=True)
        except NameError:
            self.logger.info("Unable to look up serial ports, "
                             "win32con or other python package missing!")
        return ports

    def gui_open_file(self, start_dir=None):
        '''
        GUI open file.

        :param start_dir: Directory to start in, default None
        :type start_dir: str
        :returns: Filename to open or none.
        :rtype: str
        '''
        try:
            fname, _filter, __flags = \
                win32gui.GetOpenFileNameW()  # type: ignore
            return str(fname)
        except pywintypes.error as err:  # type: ignore
            self.logger.info("gui_open_file: Failed to get filename: %s", err)
        except NameError:
            self.logger.info("Cannot open file, "
                             "win32gui or other python packages missing!")
        return None


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
        try:
            fname, _filter, _flags = \
                win32gui.GetSaveFileNameW(File=default_name)  # type: ignore
            return str(fname)
        except pywintypes.error as err:  # type: ignore
            self.logger.info("gui_save_file: Failed to get filename: %s", err)
        except NameError:
            self.logger.info("Cannot open file, "
                             "win32gui or other python packages missing!")
        return None

    def gui_select_dir(self, start_dir=None):
        '''
        GUI Select Dir.

        :param start_dir: directory to start in, default None
        :type start_dir: str
        :returns: selected directory or None
        :rtype: str
        '''
        pidl = None
        try:
            try:
                err = "No error detected"
                pidl, _display_name, _ilmage_list = \
                    shell.SHBrowseForFolder()  # type: ignore
            except pywintypes.com_error:  # type: ignore
                pass
            if not pidl:
                self.logger.info("gui_select_dir: failed to get directory: %s",
                                 err)
                return None
            fname = shell.SHGetPathFromIDList(pidl)  # type: ignore
            if not isinstance(fname, str):
                fname = fname.decode('utf-8', 'replace')
            return str(fname)
        except NameError:
            self.logger.info("Cannot open file, "
                             "win32com or other python packages missing!")
        return None

    def os_version_string(self):
        '''
        Os Version String.

        :returns: Platform version string
        :rtype: str
        '''
        vers = {"11.0": "Windows 11",
                "10.0": "Windows 10",
                "6.2": "Windows 8->10",
                "6.1": "Windows 7",
                "6.0": "Windows Vista",
                "5.2": "Windows XP 64-Bit",
                "5.1": "Windows XP",
                "5.0": "Windows 2000",
               }
        (major_version, minor_version, _build_number, _platform_id, _version) \
            = win32api.GetVersionEx() # type: ignore
        try:
            return vers.get(str(major_version) + "." + str(minor_version),
                            "Win32 (Unknown %i.%i)" %
                            (major_version, minor_version)) + \
                            " " + str(win32api.GetVersionEx()) # type: ignore
        except NameError:
            self.logger.info("Cannot Get Windows Version, "
                             "win32api or other python packages missing!")
        return "Windows Unknown."

    def play_sound(self, soundfile):
        '''
        Play Sound.

        :param soundfile: file to play sound from
        :type soundfile: str
        '''
        try:
            winsound.PlaySound(soundfile,              # type: ignore
                               winsound.SND_FILENAME)  # type: ignore
        except NameError:
            self.logger.info("Cannot play sound, "
                             "winsound or other python packages missing!")


def do_test():
    '''Unit Test.'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)

    logger = logging.getLogger("dplatform")
    pform = Platform.get_platform()

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
