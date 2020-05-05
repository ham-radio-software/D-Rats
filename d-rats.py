#!/usr/bin/python
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

import sys
import os
from optparse import OptionParser

import traceback
import gtk

sys.path.insert(0, os.path.join("/usr/share", "d-rats"))

#import module to have spelling correction in chat and email applications
from d_rats import utils, spell 
spell.get_spell().test()

IGNORE_ALL=False

# here we design the window which usually comes out at the beginning asking 
# to "ignore/ignore all" the exceptions
def handle_exception(exctyp, value, tb):
    
    # this eventually starts the initial window with the list of errors and the
    # buttons to open log or ignore errors

    global IGNORE_ALL

    if exctyp is KeyboardInterrupt or IGNORE_ALL:
        return original_excepthook(exctyp, value, tb)

    gtk.gdk.pointer_ungrab()
    gtk.gdk.keyboard_ungrab()

    _trace = traceback.format_exception(exctyp, value, tb)
    trace = os.linesep.join(_trace)

    print("---- GUI Exception ----\n%s\n---- End ----\n" % trace)

    msg = """
<b><big>D-RATS has encountered an error.</big></b>
This may be non-fatal, so you may click <b>Ignore</b> below to attempt to continue running.  Otherwise, click 'Quit' to terminate D-RATS now. If you are planning to file a bug for this issue, please click <b>Debug Log</b> below and include the contents in the bug tracker.
If you need to ignore all additional warnings for this session, click <b>Ignore All</b>.  However, please reproduce and report the issue when possible.
"""

    def extra(dialog):
        dialog.add_button(_("Debug Log"), gtk.RESPONSE_HELP);
        dialog.add_button(_("Ignore"), gtk.RESPONSE_CLOSE);
        dialog.add_button(_("Ignore All"), -1);
        dialog.add_button(gtk.STOCK_QUIT, gtk.RESPONSE_CANCEL);
        dialog.set_default_response(gtk.RESPONSE_CANCEL)

    while True:
        r = utils.make_error_dialog(msg, trace,
                                    gtk.BUTTONS_NONE,
                                    gtk.MESSAGE_ERROR,
                                    extra=extra)
        if r == gtk.RESPONSE_CANCEL:
            sys.exit(1)
        elif r == gtk.RESPONSE_CLOSE:
            break
        elif r == -1:
            IGNORE_ALL=True
            break
        elif r == gtk.RESPONSE_HELP:
            p = dplatform.get_platform()
            p.open_text_file(p.config_file("debug.log"))


def install_excepthook():
    # saves away the original value of sys.excepthook
    global original_excepthook
    original_excepthook = sys.excepthook
    #invoke the manager of the initial windows to ask user what to do with exceptions
    sys.excepthook = handle_exception

def uninstall_excepthook():
    # restores the original value of sys.excepthook
    global original_excepthook
    sys.excepthook = ignore_exception

def ignore_exception(exctyp, value, tb):
    return
#-------------- main d-rats module -----------------    def set_defaults(self):---
#
if __name__ == "__main__":
    #
    # lets parse the options passed from command line
    o = OptionParser()
    o.add_option("-s", "--safe",
                 dest="safe",
                 action="store_true",
                 help="Safe mode (ignore configuration)")
    o.add_option("-c", "--config",
                 dest="config",
                 help="Use alternate configuration directory")
    o.add_option("-p", "--profile",
                 dest="profile",
                 action="store_true",
                 help="Enable profiling")
    (opts, args) = o.parse_args()

    # import the platform module - this will setup all the proper parameters for the different OSs
    from d_rats import dplatform

    if opts.config:
        print("D-Rats     : re-config option found -- Reconfigure D-rats")
        dplatform.get_platform(opts.config)

    # import the D-Rats main application
    from d_rats import mainapp

    #stores away the value of sys.excepthook
    install_excepthook()

    import libxml2
    libxml2.debugMemory(1)

    # create the mainapp with the basic options 
    app = mainapp.MainApp(safe=opts.safe)

    # finally let's open the default application triggering it differently if we 
    # want to profile it (which is running the app under profile control to see what happens) 
    if opts.profile :
        import cProfile
        cProfile.run('app.main()')
    else:
        #execute the main app
        rc = app.main()
        #restores  the original value of sys.excepthook
        uninstall_excepthook()
        libxml2.dumpMemory()
        sys.exit(rc)

