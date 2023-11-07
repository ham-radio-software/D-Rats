#!/usr/bin/env python3
# "d-rats.py" does not comply with Snake Case naming, so must suppress this.
# pylint: disable=invalid-name
'''d-rats main program'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# review 2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Python3 conversion Copyright 2022 John Malmberg <wb8tyw@qsl.net>
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

import argparse
import gettext
import logging
import os
import sys
import traceback

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

# Make sure no one tries to run this with privileges.
try:
    if os.geteuid() == 0:
        print("Refusing to run with unneeded privileges!")
        sys.exit(1)
except AttributeError:
    pass

from d_rats.version import __version__
from d_rats.version import DRATS_VERSION
from d_rats.dplatform import Platform
from d_rats import mainapp

# Temporary to allow enabling serial port logging.
from d_rats.comm import SWFSerial

# Default gettext function which is needed for pylance
# This global variable will be overridden by the mainapp module.
_ = gettext.gettext

MODULE_LOGGER = logging.getLogger("D-Rats")

sys.path.insert(0, os.path.join("/usr/share", "d-rats"))

# import module to have spelling correction in chat and email applications
from d_rats import utils, spell

spell.get_spell().test()

IGNORE_ALL = False

# here we design the window which usually comes out at the beginning asking
# to "ignore/ignore all" the exceptions

def handle_exception(except_type, value, trace_back):
    '''
    Handle Exception.

    :param except_type: Exception type
    :type except_type: type
    :param value: Exception value
    :type value: Exception
    :param trace_back: Traceback
    :type trace_back: traceback
    '''

    # this eventually starts the initial window with the list of errors and the
    # buttons to open log or ignore errors

    # This currently needs to a global statement.
    # pylint: disable=global-statement
    global IGNORE_ALL

    if except_type is KeyboardInterrupt or IGNORE_ALL:
        return sys.__excepthook__(except_type, value, trace_back)

    # Gdk.pointer_ungrab(Gdk.CURRENT_TIME)
    # Gdk.keyboard_ungrab(Gdk.CURRENT_TIME)
    # WB8TYW: Gdk.pointer_ungrab and Gdk_keyboard_ungrab are marked as
    # deprecated.  Documentation says to use Gdk.Seat.ungrab().
    # At this point, we do not have a seat object use and would
    # need to rework things a bit.
    # Other documentation indicates that most grabs and un-grabs may
    # not be needed for Gtk 3

    _trace = traceback.format_exception(except_type, value, trace_back)
    trace = os.linesep.join(_trace)

    MODULE_LOGGER.info("---- GUI Exception ----\n%s\n---- End ----\n",
                       stack_info=True)

    msg = """
<b><big>D-RATS has encountered an error.</big></b>
This may be non-fatal, so you may click <b>Ignore</b> below to attempt to
continue running.  Otherwise, click 'Quit' to terminate D-RATS now.
If you are planning to file a bug for this issue, please click
<b>Debug Log</b> below and include the contents in the bug tracker.
If you need to ignore all additional warnings for this session, click
<b>Ignore All</b>.  However, please reproduce and report the issue when
possible.
"""

    def extra(dialog):
        dialog.add_button(_("Debug Log"), Gtk.ResponseType.HELP)
        dialog.add_button(_("Ignore"), Gtk.ResponseType.CLOSE)
        dialog.add_button(_("Ignore All"), -1)
        dialog.add_button(_("Quit"), Gtk.ResponseType.CANCEL)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)

    while True:
        response = utils.make_error_dialog(msg, trace,
                                           Gtk.ButtonsType.NONE,
                                           Gtk.MessageType.ERROR,
                                           extra=extra)
        if response == Gtk.ResponseType.CANCEL:
            sys.exit(1)
        if response == Gtk.ResponseType.CLOSE:
            break
        if response == -1:
            IGNORE_ALL = True
            break
        if response == Gtk.ResponseType.HELP:
            platform = Platform.get_platform()
            platform.open_text_file(platform.config_file("debug.log"))


def install_excepthook():
    '''install Excepthook.'''
    sys.excepthook = handle_exception


def uninstall_excepthook():
    '''Uninstall Excepthook.'''
    # restores the original value of sys.excepthook
    sys.excepthook = sys.__excepthook__


def main():
    '''D-Rats Main module.'''

    platform = Platform.get_platform()
    def_config_dir = platform.config_dir()

    # pylint wants at least 2 public methods, but we do not need them
    # since this is extending another class.
    # pylint: disable=too-few-public-methods
    class LoglevelAction(argparse.Action):
        '''
        Custom Log Level action.

        This allows entering a log level command line argument
        as either a known log level name or a number.
        '''

        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("nargs is not allowed")
            argparse.Action.__init__(self, option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_strings=None):
            level = values.upper()
            level_name = logging.getLevelName(level)
            # Contrary to documentation, the above returns for me
            # an int if given a name or number of a known named level and
            # str if given a number for a level with out a name.
            if isinstance(level_name, int):
                level_name = level
            elif level_name.startswith('Level '):
                level_name = int(level)
            setattr(namespace, self.dest, level_name)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=_('DRATS'))
    parser.add_argument('-c', '--config',
                        default=def_config_dir,
                        help="Use alternate configuration directory")

    # While loglevel actually returns an int, it needs to be set to the
    # default type of str for the action routine to handle both named and
    # numbered levels.
    parser.add_argument('--loglevel',
                        action=LoglevelAction,
                        default='INFO',
                        help=_('LOGLEVEL TO TEST WITH'))

    parser.add_argument("-p", "--profile",
                        action="store_true",
                        help="Enable profiling")

    parser.add_argument("-s", "--safe",
                        action="store_true",
                        help="Safe mode (ignore configuration)")

    parser.add_argument("-v", "--version",
                        action="store_true",
                        help="Show version.")

    parser.add_argument("--sdebug",
                        action="store_true",
                        help="Log serial port data.")

    args = parser.parse_args()

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=args.loglevel)
    if args.version:
        print("version: %s" % DRATS_VERSION)
        sys.exit()

    if args.config:
        MODULE_LOGGER.info("main: re-config option found -- Reconfigure D-rats")
        MODULE_LOGGER.info("main: args.config = %s", args.config)
        platform.set_config_dir(args.config)

    # This is temporary for debugging serial port radio transfers
    if args.sdebug:
        serial_log_file = platform.log_file('serial')
        SWFSerial.set_log_file(serial_log_file)

     # stores away the value of sys.excepthook
    install_excepthook()

    # create the mainapp with the basic options
    app = mainapp.MainApp(safe=args.safe)

    MODULE_LOGGER.info("main: reloading app\n\n")
    # finally let's open the default application triggering it differently if
    # we want to profile it (which is running the app under profile control to
    # see what happens)
    if args.profile:
        MODULE_LOGGER.info("main: Executing with cprofile")
        # Contrary to pylint, we do not want to import this unless needed.
        # pylint: disable=import-outside-toplevel
        import cProfile
        cProfile.runctx('app.main()', globals(), locals())
    else:
        # execute the main app
        # result_code = app.main()
        result_code = 0
        app.main()
        uninstall_excepthook()
        sys.exit(result_code)


if __name__ == "__main__":
    main()
