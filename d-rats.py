#!/usr/bin/python
# pylint: disable=invalid-name
'''d-rats main program'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# review 2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
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
import sys
import os
import logging
import gettext

# pylint: disable=deprecated-module
from optparse import OptionParser

import traceback
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk

# pylint: disable=invalid-name
lang = gettext.translation("D-RATS",
                           localedir="./locale",
                           fallback=True)
lang.install()
_ = lang.gettext

from d_rats.dplatform import get_platform
#importing print() wrapper

sys.path.insert(0, os.path.join("/usr/share", "d-rats"))

#import module to have spelling correction in chat and email applications
from d_rats import utils, spell

spell.get_spell().test()

IGNORE_ALL = False

# here we design the window which usually comes out at the beginning asking
# to "ignore/ignore all" the exceptions


logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                    datefmt="%m/%d/%Y %H:%M:%S",
                    level=logging.INFO)
# pylint: disable=invalid-name
module_logger = logging.getLogger("D-Rats")

def handle_exception(exctyp, value, tb):
    '''
    Handle Exception.

    :param exctyp: Exception type,
    :param value: Exception value
    :param tb: Traceback
    '''

    # this eventually starts the initial window with the list of errors and the
    # buttons to open log or ignore errors

    # pylint: disable=global-statement
    global IGNORE_ALL

    if exctyp is KeyboardInterrupt or IGNORE_ALL:
        return original_excepthook(exctyp, value, tb)

    Gdk.pointer_ungrab(Gdk.CURRENT_TIME)
    Gdk.keyboard_ungrab(Gdk.CURRENT_TIME)
    # WB8TYW: Gdk.pointer_ungrab and Gdk_keyboard_ungrab are marked as
    # deprecated.  Documentation says to use Gdk.ungrab() instead.
    # That generates a AttributeError, Gdk has no attribute 'ungrab'.
    # Gdk.ungrab()

    _trace = traceback.format_exception(exctyp, value, tb)
    trace = os.linesep.join(_trace)

    module_logger.info("---- GUI Exception ----\n%s\n---- End ----\n",
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
        # dialog.add_button(Gtk.STOCK_QUIT, Gtk.ResponseType.CANCEL)
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
            platform = get_platform()
            platform.open_text_file(platform.config_file("debug.log"))


def install_excepthook():
    '''install Excepthook.'''
    # saves away the original value of sys.excepthook
    # pylint: disable=global-variable-undefined
    global original_excepthook
    original_excepthook = sys.excepthook
    # invoke the manager of the initial windows to ask user what to do with
    # exceptions
    # sys.excepthook = handle_exception


def uninstall_excepthook():
    '''Uninstall Excepthook.'''
    # restores the original value of sys.excepthook
    # pylint: disable=global-variable-undefined
    global original_excepthook
    # sys.excepthook = ignore_exception


def ignore_exception(_exctyp, _value, _tb):
    '''
    Ignore exception.

    :param _exctype: Exception type, unused
    :param _value: Exception Value, unused
    :param _tb: Traceback, unused
    '''
    return
#-------------- main d-rats module -----------------
# --- def set_defaults(self):---
#


def main():
    '''D-Rats Main module.'''
    #
    # lets parse the options passed from command line
    ops = OptionParser()
    ops.add_option("-s", "--safe",
                   dest="safe",
                   action="store_true",
                   help="Safe mode (ignore configuration)")
    ops.add_option("-c", "--config",
                   dest="config",
                   help="Use alternate configuration directory")
    ops.add_option("-p", "--profile",
                   dest="profile",
                   action="store_true",
                   help="Enable profiling")
    (opts, _args) = ops.parse_args()

    # Eventually this will be a config option/command line
    logging.basicConfig(level=logging.INFO)
    if opts.config:
        module_logger.info("main: re-config option found -- Reconfigure D-rats")
        get_platform(opts.config)

    # import the D-Rats main application
    from d_rats import mainapp

    # stores away the value of sys.excepthook
    install_excepthook()

    # create the mainapp with the basic options
    app = mainapp.MainApp(safe=opts.safe)

    module_logger.info("main: reloading app\n\n")
    # finally let's open the default application triggering it differently if
    # we want to profile it (which is running the app under profile control to
    # see what happens)
    if opts.profile:
        module_logger.info("main: Executing with cprofile")
        import cProfile
        cProfile.run('app.main()')
    else:
        #execute the main app
        # result_code = app.main()
        result_code = 0
        app.main()
        #restores  the original value of sys.excepthook
        uninstall_excepthook()
        # libxml2.dumpMemory()
        sys.exit(result_code)


if __name__ == "__main__":
    main()
