'''Form.'''

from __future__ import absolute_import
from d_rats.sessions import base
from d_rats.sessions import file as sessions_file


class FormTransferSession(sessions_file.FileTransferSession):
    '''Form Transfer Session.'''

    type = base.T_FORMXFER
