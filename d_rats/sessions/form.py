'''Form.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Python3 update Copyright 2021 John Malmberg <wb8tyw@qsl.net>
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

import logging
from d_rats.sessions import base
from d_rats.sessions import file as sessions_file

class FormTransferSession(sessions_file.FileTransferSession):
    '''Form Transfer Session.'''

    type = base.T_FORMXFER

    def __init__(self, name, status_cb=None, **kwargs):
        sessions_file.FileTransferSession.__init__(self, name, **kwargs)
        self.logger = logging.getLogger("FormTransferSession")
