'''Misc Widgets.'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


def make_choice(options, editable=True, default=None):
    '''
    Make Choice.

    :param options: options
    :type options: List[str]
    :param editable: Is text editable, Default True
    :type editable: bool
    :param default: Default text to select, Default None
    :type default: str
    :returns: selection dialog
    :rtype: :class:`Gtk.ComboBoxText`
    '''
    if editable:
        sel = Gtk.ComboBoxText.new_with_entry()
    else:
        sel = Gtk.ComboBoxText.new()

    for opt in options:
        sel.append_text(opt)

    if default:
        try:
            idx = options.index(default)
            sel.set_active(idx)
        except ValueError:
            pass
    return sel
